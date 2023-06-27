"""
Wrapper for Radarr
"""
import os
from typing import List
import logging

import humanize
from pyarr import RadarrAPI
from thefuzz import fuzz

logger = logging.getLogger(__name__)

USER_TAG_MAP = {
    "simple_harmonic_motion": "sean",
    "elzibubble": "alexis",
    "bakatron": "nick",
    "spike6112": "spike",
    "seraphaile": "mark",
    "hobbygrade": "harry",
}


def _filter_movies(movies, *args) -> List[dict]:
    string_match = ' '.join(args)
    movies = sorted(movies, key=lambda k: fuzz.partial_ratio(k['title'], string_match), reverse=True)
    movies = movies[:10]
    for movie in movies:
        movie['fuzzy_score'] = fuzz.partial_ratio(movie['title'], string_match)

    return movies


def radarr_help_text():
    help_message = """!radarr [ status | list | me | tag <id> | untag <id> | search <title> | add <imdb id> ]
status          - show status of radarr
list [title]    - list all movies in radarr [by fuzzy title match]
me [title]      - show your tagged movies [by fuzzy title match]
tag <id>        - tag a movie with your discord username
untag <id>      - untag a movie with your discord username
search <title>  - search for a movie by fuzzy title match
add <imdb id>   - add a movie to radarr"""

    yield help_message


class Radarr:
    api: RadarrAPI

    def __init__(self, url: str, api_key: str):
        self.api = RadarrAPI(url, api_key)

    def status(self):
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

        # List untagged movies
        if untagged_count > 0:
            text = ""
            for movie in untagged_movies:
                text += f"> {movie['id']:>5}: {movie['title']} ({movie['year']})\n"
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
            all_movies_list += f"{movie['id']:>5}: {movie['title']} ({movie['year']}){fuzzy_string}\n"
            if len(all_movies_list) > 1800:
                yield all_movies_list
                all_movies_list = ""

        yield all_movies_list

    def _lookup_user_id(self, username: str):
        if username not in USER_TAG_MAP:
            raise ValueError(f"User {username} not found in USER_TAG_MAP")

        tags = self.api.get_tag()
        for tag in tags:
            if tag["label"] == USER_TAG_MAP[username]:
                return tag["id"]

    def me(self, username: str, *args):
        user_id = self._lookup_user_id(username)

        all_movies = self.api.get_movie()

        if len(args) > 0:
            all_movies = _filter_movies(all_movies, *args)
        else:
            all_movies = sorted(all_movies, key=lambda k: k['title'])

        all_movies_list = ""
        for movie in all_movies:
            if user_id in movie["tags"]:
                fuzzy_string = ""
                if 'fuzzy_score' in movie:
                    fuzzy_string = f" (fuzzy score: {movie['fuzzy_score']})"
                all_movies_list += f"{movie['id']:>5}: {movie['title']} ({movie['year']}){fuzzy_string}\n"

        return f"{all_movies_list}"

    def tag(self, username: str, *args):
        user_id = self._lookup_user_id(username)

        if len(args) == 0:
            return "Please provide a movie ID to tag"

        movie_id = args[0]

        movie = self.api.get_movie(id_=movie_id)

        if movie is None:
            return "No movie found with ID {movie_id}"

        if user_id in movie["tags"]:
            return f"Movie {movie['title']} ({movie['year']}) is already tagged for you"

        movie["tags"].append(user_id)
        movie = self.api.upd_movie(movie)

        return f"Tagged {movie['title']} ({movie['year']})"

    def untag(self, username: str, *args):
        user_id = self._lookup_user_id(username)

        if len(args) == 0:
            return "Please provide a movie ID to untag"

        movie_id = args[0]

        movie = self.api.get_movie(id_=movie_id)

        if movie is None:
            return "No movie found with ID {movie_id}"

        if user_id not in movie["tags"]:
            return f"Movie {movie['title']} ({movie['year']}) is not tagged for you"

        movie["tags"].remove(user_id)
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

        for movie in movies:
            text = f"{movie['imdbId']} {movie['title']} ({movie['year']})\n"
            text += f"> {movie['overview']}"
            yield text

    def add_movie(self, username, *args):
        if len(args) == 0:
            yield "Please provide an IMDB ID (tt...)"
            return

        imdb_id = args[0]

        movie = self.api.lookup_movie(term=f"imdb:{imdb_id}")

        if movie is None:
            yield f"No movie found for IMDB ID {imdb_id}"
            return

        if len(movie) > 1:
            yield f"Found multiple matches for IMDB ID {imdb_id}"
            return

        movie = movie[0]

        root_dir = self.api.get_root_folder()[0]
        quality_profile = self._get_quality_profile()
        user_id = self._lookup_user_id(username)

        movie = self.api.add_movie(
            root_dir=root_dir['path'],
            movie=movie,
            quality_profile_id=quality_profile['id'],
            tags=[user_id]
        )

        yield f"Added {movie['title']} ({movie['year']})"

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
