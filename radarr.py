"""
Wrapper for Radarr
"""
from typing import List

import humanize
from pyarr import RadarrAPI
from thefuzz import fuzz

USER_TAG_MAP = {
    "simple_harmonic_motion": "sean",
    "elzibubble": "alexis",
    "bakatron": "nick",
    "spike6112": "spike",
    "seraphaile": "mark",
}


def _filter_movies(movies, *args) -> List[dict]:
    string_match = ' '.join(args)
    movies = sorted(movies, key=lambda k: fuzz.partial_ratio(k['title'], string_match), reverse=True)
    movies = movies[:10]
    for movie in movies:
        movie['fuzzy_score'] = fuzz.partial_ratio(movie['title'], string_match)

    return movies


class Radarr:
    api: RadarrAPI

    def __init__(self, url: str, api_key: str):
        self.api = RadarrAPI(url, api_key)

    def status(self):
        all_movies = self.api.get_movie()
        count = len(all_movies)

        untagged_count = 0
        total_size = 0
        untagged_size = 0
        for movie in all_movies:
            total_size += movie["sizeOnDisk"]
            if len(movie["tags"]) == 0:
                untagged_size += movie["sizeOnDisk"]
                untagged_count += 1

        # Convert sizes to human-readable
        h_total_size = humanize.naturalsize(total_size)
        h_untagged_size = humanize.naturalsize(untagged_size)

        # Setup untagged message
        if untagged_count == 0:
            untagged_message = "(all tagged)"
        else:
            untagged_message = f"({untagged_count} untagged totalling {h_untagged_size})"

        return f"There are {count} movies totalling {h_total_size} {untagged_message}"

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
