#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# License: GPL
# Author : Vitiko

import json
import logging
import os
import random
import sys
from datetime import datetime
from functools import reduce

import click
import facepy
import requests
from facepy import GraphAPI

import kinobot.exceptions as exceptions
from kinobot.config import FACEBOOK, FILM_COLLECTION
from kinobot.db import (
    block_user,
    get_list_of_movie_dicts,
    get_requests,
    insert_request_info_to_db,
    update_request_to_used,
)
from kinobot.discover import discover_movie
from kinobot.request import Request
from kinobot.utils import get_collage, get_poster_collage

COMMANDS = ("!req", "!country", "!year", "!director")
WEBSITE = "https://kino.caretas.club"
FACEBOOK_URL = "https://www.facebook.com/certifiedkino"
GITHUB_REPO = "https://github.com/vitiko98/kinobot"
MOVIES = get_list_of_movie_dicts()
TIME = datetime.now().strftime("Automatically executed at %H:%M GMT-4")
FB = GraphAPI(FACEBOOK)

logger = logging.getLogger(__name__)


def check_directory():
    if not os.path.isdir(FILM_COLLECTION):
        sys.exit(f"Collection not mounted: {FILM_COLLECTION}")


def save_images(pil_list):
    """
    :param pil_list: list PIL.Image objects
    """
    nums = random.sample(range(10000), len(pil_list))
    names = [f"/tmp/{i}.png" for i in nums]
    for image, name in zip(pil_list, names):
        image.save(name)
    return names


def post_multiple(images, description, published=False):
    """
    :param images: list of image paths
    :param description: description
    :param published
    """
    logger.info("Post multiple images")
    photo_ids = []
    for image in images:
        photo_ids.append(
            {
                "media_fbid": FB.post(
                    path="me/photos", source=open(image, "rb"), published=False
                )["id"]
            }
        )
    final = FB.post(
        path="me/feed",
        attached_media=json.dumps(photo_ids),
        message=description,
        published=published,
    )
    logger.info(f"Posted: {FACEBOOK_URL}/posts/{final['id'].split('_')[-1]}")
    return final["id"]


def post_request(
    images, movie_info, request, request_command, is_multiple=True, published=False
):
    """
    :param images: list of image paths
    :param movie_info: movie dictionary
    :param request: request dictionary
    :param request_command: request command string
    :param is_multiple
    :param published
    """
    pretty_title = movie_info["title"]
    if (
        movie_info["title"].lower() != movie_info["original_title"].lower()
        and len(movie_info["original_title"]) < 45
    ):
        pretty_title = f"{movie_info['original_title']} [{movie_info['title']}]"

    title = (
        f"{pretty_title} ({movie_info['year']})\nDirector: "
        f"{movie_info['director']}\nCategory: {movie_info['category']}"
    )

    description = (
        f"{title}\n\nRequested by {request['user']} ({request_command}"
        f"{request['comment']})\n\n{TIME}\nThis bot is open source: {GITHUB_REPO}"
    )

    if len(images) > 1:
        return post_multiple(images, description, published)

    logger.info("Posting single image")

    post_id = FB.post(
        path="me/photos",
        source=open(images[0], "rb"),
        published=published,
        message=description,
    )
    logger.info(f"Posted: {FACEBOOK_URL}/photos/{post_id['id']}")
    return post_id["id"]


def comment_post(post_id, published=False):
    """
    :param post_id: Facebook post ID
    :param published
    """
    if not published:
        return
    poster_collage = get_poster_collage(MOVIES)
    poster_collage.save("/tmp/tmp_collage.png")
    com = (
        f"Explore the collection ({len(MOVIES)} Movies):\n{WEBSITE}\n"
        f"Are you a top user?\n{WEBSITE}/users/all\n"
        'Request examples:\n"!req Taxi Driver [you talking to me?]"\n"'
        '!req Stalker [20:34]"\n"!req A Man Escaped [21:03] [23:02]"'
    )
    FB.post(
        path=post_id + "/comments",
        source=open("/tmp/tmp_collage.png", "rb"),
        message=com,
    )
    logger.info("Commented")


def notify(comment_id, reason=None, published=True):
    """
    :param comment_id: Facebook comment ID
    :param reason: exception string
    """
    if not published:
        return
    if not reason:
        noti = (
            "202: Your request was successfully executed.\n"
            f"Are you in the list of top users? {WEBSITE}/users/all\n"
            f"Check the complete list of movies: {WEBSITE}"
        )
    else:
        if "offen" in reason.lower():
            noti = (
                "An offensive word has been detected when processing your request. "
                "You are blocked.\n\nSend a PM if you believe this was accidental."
            )
        else:
            noti = (
                f"Kinobot returned an error: {reason}. Please, don't forget "
                "to check the list of available films and instructions"
                f" before making a request: {WEBSITE}"
            )
    try:
        FB.post(path=comment_id + "/comments", message=noti)
    except facepy.exceptions.FacebookError:
        logger.info("The comment was deleted")


def get_images(comment_dict, is_multiple):
    frames = []
    for frame in comment_dict["content"]:
        request = Request(comment_dict["movie"], frame, MOVIES, is_multiple)
        if request.is_minute:
            request.handle_minute_request()
        else:
            request.handle_quote_request()
        frames.append(request)

    final_image_list = [im.pill for im in frames]
    single_image_list = reduce(lambda x, y: x + y, final_image_list)
    if len(single_image_list) < 4:
        single_image_list = [get_collage(single_image_list, False)]
    return save_images(single_image_list), frames


def handle_requests(published=True):
    logger.info(f"Starting request handler (published: {published})")
    sys.exit()
    requests_ = get_requests()
    random.shuffle(requests_)
    for m in requests_:
        try:
            block_user(m["user"], check=True)
            request_command = m["type"]

            if len(m["content"]) > 20 or len(m["content"][0]) > 130:
                raise exceptions.TooLongRequest

            logger.info(f"Request command: {request_command} {m['comment']}")

            if "req" not in request_command:
                if len(m["content"]) != 1:
                    raise exceptions.BadKeywords

                req_dict = discover_movie(
                    m["movie"], request_command.replace("!", ""), m["content"][0]
                )
                m["movie"] = req_dict["title"] + " " + str(req_dict["year"])
                m["content"] = [req_dict["quote"]]

            is_multiple = len(m["content"]) > 1
            final_imgs, frames = get_images(m, is_multiple)
            post_id = post_request(
                final_imgs, frames[0].movie, m, request_command, is_multiple, published
            )

            try:
                comment_post(post_id, published)
            except requests.exceptions.MissingSchema:
                logger.error("Error making the collage")

            notify(m["id"], None, published)

            insert_request_info_to_db(frames[0].movie, m["user"])
            update_request_to_used(m["id"])
            logger.info("Request finished successfully")
            break
        except exceptions.RestingMovie:
            # ignore recently requested movies
            continue
        except (FileNotFoundError, OSError) as error:
            # to check missing or corrupted files
            logger.error(error, exc_info=True)
            continue
        except exceptions.BlockedUser:
            update_request_to_used(m["id"])
        except Exception as error:
            logger.error(error, exc_info=True)
            if not published:
                continue
            update_request_to_used(m["id"])
            message = type(error).__name__
            if "offens" in message.lower():
                block_user(m["user"])
            notify(m["id"], message, published)


@click.command("post")
@click.option("-t", "--test", is_flag=True, help="don't publish to Facebook")
def post(test):
    " Find a valid request and post it to Facebook. "
    logger.info(f"Test mode: {test}")
    check_directory()
    handle_requests(published=not test)
    logger.info("FINISHED\n" + "#" * 70)