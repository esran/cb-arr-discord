"""
Wrapper for Radarr
"""
import logging
import os
from typing import List, Optional, Dict, Any

import humanize
import pyarr.exceptions
from pyarr import RadarrAPI
from thefuzz import fuzz

logger = logging.getLogger(__name__)


def _filter_movies(movies, *args) -> List[dict]:
    string_match = ' '.join(args)
    movies = sorted(movies, key=lambda k: fuzz.partial_ratio(k['title'], string_match), reverse=True)
    movies = movies[:10]
    for movie in movies:
        movie['fuzzy_score'] = fuzz.partial_ratio(movie['title'], string_match)

    return movies


def radarr_help_text():
    help_message = """!radarr [ status | list | me | tag <tmdb id> | untag <tmdb id> | search <title> | add <tmdb id> ]
status [+]      - show status of radarr [+ list untagged movies]
list [title]    - list all movies in radarr [by fuzzy title match]
me [title]      - show your tagged movies [by fuzzy title match]
tag <tmdb id>   - tag a movie with your discord username
untag <tmdb id> - untag a movie with your discord username
search <title>  - search for a new movie by fuzzy title match
add <tmdb id>   - add a new movie to radarr"""

    yield help_message


def movie_text_line(movie):
    return f"{movie['tmdbId']:>7}: {movie['title']} ({movie['year']})"


class Radarr:
    api: RadarrAPI

    def __init__(self, url: str, api_key: str):
        self.api = RadarrAPI(url, api_key)

    def status(self, *args):
        all_movies = self.api.get_movie()
        count = len(all_movies)

        total_size = 0
        untagged_size = 0
        untagged_movies = []
        for movie in all_movies:
            total_size += movie["sizeOnDisk"]
            if len(movie["tags"]) == 0:
                untagged_movies.append(movie)
                untagged_size += movie["sizeOnDisk"]

        # Convert sizes to human-readable
        h_total_size = humanize.naturalsize(total_size)
        h_untagged_size = humanize.naturalsize(untagged_size)

        # Setup untagged message
        untagged_count = len(untagged_movies)
        if untagged_count == 0:
            untagged_message = "(all tagged)"
        else:
            untagged_message = f"({untagged_count} untagged totalling {h_untagged_size})"

        yield f"There are {count} movies totalling {h_total_size} {untagged_message}"

        # Optionally, list untagged movies
        if len(args) > 0 and args[0] == "+":
            if untagged_count > 0:
                text = ""
                for movie in untagged_movies:
                    text += movie_text_line(movie) + "\n"
                    if len(text) > 1800:
                        yield text
                        text = ""

                yield text
                yield "Use `!radarr tag <id>` to tag a movie for yourself"

    def list(self, *args):
        all_movies = self.api.get_movie()

        if len(args) > 0:
            all_movies = _filter_movies(all_movies, *args)
        else:
            all_movies = sorted(all_movies, key=lambda k: k['title'])

        all_movies_list = ""
        for movie in all_movies:
            fuzzy_string = ""
            if 'fuzzy_score' in movie:
                fuzzy_string = f" (fuzzy score: {movie['fuzzy_score']})"
            all_movies_list += movie_text_line(movie) + fuzzy_string + "\n"
            if len(all_movies_list) > 1800:
                yield all_movies_list
                all_movies_list = ""

        yield all_movies_list

    def _get_tag_id(self, label: str) -> Optional[int]:
        tags = self.api.get_tag()
        for tag in tags:
            if tag["label"] == label:
                return tag["id"]
        return None

    def _lookup_user_tag_id(self, username: str) -> int:
        tag_id = self._get_tag_id(username)

        if tag_id is None:
            self.api.create_tag(label=username)

        tag_id = self._get_tag_id(username)

        if tag_id is None:
            raise ValueError('Unable to create tag')

        return tag_id

    def me(self, username: str, *args):
        tag_id = self._lookup_user_tag_id(username)

        all_movies = self.api.get_movie()

        if len(args) > 0:
            all_movies = _filter_movies(all_movies, *args)
        else:
            all_movies = sorted(all_movies, key=lambda k: k['title'])

        all_movies_list = ""
        for movie in all_movies:
            if tag_id in movie["tags"]:
                fuzzy_string = ""
                if 'fuzzy_score' in movie:
                    fuzzy_string = f" (fuzzy score: {movie['fuzzy_score']})"
                all_movies_list += movie_text_line(movie) + fuzzy_string + "\n"
                if len(all_movies_list) > 1800:
                    yield all_movies_list
                    all_movies_list = ""

        if all_movies_list != "":
            yield all_movies_list

    def _get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        movies = self.api.get_movie(id_=movie_id, tmdb=True)

        if movies is None or len(movies) == 0:
            return None

        if len(movies) > 1:
            return None

        return movies[0]

    def tag(self, username: str, *args):
        tag_id = self._lookup_user_tag_id(username)

        if len(args) == 0:
            return "Please provide a movie ID to tag"

        movie_id = args[0]

        movie = self._get_movie_by_id(movie_id)
        if movie is None:
            return f"Movie could not be identified using ID {movie_id}"

        if tag_id in movie["tags"]:
            return f"Movie {movie['title']} ({movie['year']}) is already tagged for you"

        movie["tags"].append(tag_id)
        movie = self.api.upd_movie(movie)

        return f"Tagged {movie['title']} ({movie['year']})"

    def untag(self, username: str, *args):
        tag_id = self._lookup_user_tag_id(username)

        if len(args) == 0:
            return "Please provide a movie ID to untag"

        movie_id = args[0]

        movie = self._get_movie_by_id(movie_id)
        if movie is None:
            return f"Movie could not be identified using ID {movie_id}"

        if tag_id not in movie["tags"]:
            return f"Movie {movie['title']} ({movie['year']}) is not tagged for you"

        movie["tags"].remove(tag_id)
        movie = self.api.upd_movie(movie)

        return f"Untagged {movie['title']} ({movie['year']})"

    def search(self, *args):
        if len(args) == 0:
            yield "Please provide a search string"
            return

        search_string = ' '.join(args)

        movies = self.api.lookup_movie(term=search_string)

        if movies is None:
            yield "No movies found for search string {search_string}"
            return

        text = ""
        for movie in movies:
            text += movie_text_line(movie) + "\n"
            if len(text) > 1800:
                yield text
                text = ""

        yield text

    def add_movie(self, username, *args):
        if len(args) == 0:
            yield "Please provide the TMDB ID"
            return

        tmdb_id = args[0]

        movie = self.api.lookup_movie(term=f"tmdb:{tmdb_id}")

        if movie is None:
            yield f"No movie found for TMDB ID {tmdb_id}"
            return

        if len(movie) > 1:
            yield f"Found multiple matches for TMDB ID {tmdb_id}"
            return

        movie = movie[0]

        root_dir = self.api.get_root_folder()[0]
        quality_profile = self._get_quality_profile()
        tag_id = self._lookup_user_tag_id(username)

        try:
            movie = self.api.add_movie(
                root_dir=root_dir['path'],
                movie=movie,
                quality_profile_id=quality_profile['id'],
                tags=[tag_id]
            )
            yield f"Added {movie['title']} ({movie['year']})"
        except pyarr.exceptions.PyarrBadRequest as e:
            if "This movie has already been added" in str(e):
                yield f"Movie {movie['title']} ({movie['year']}) is already added"
            else:
                yield f"Error adding movie: {e}"

    def _get_quality_profile(self):
        desired_profile = os.environ.get("RADARR_QUALITY_PROFILE", 'Bluray|WEB-1080p')
        profiles = self.api.get_quality_profile()

        chosen = None

        if desired_profile is None:
            chosen = profiles[0]

        else:
            for profile in profiles:
                if profile["name"] == desired_profile:
                    chosen = profile

        if chosen is None:
            chosen = profiles[0]

        logger.info(f"Using quality profile {chosen['name']}")
        return chosen
