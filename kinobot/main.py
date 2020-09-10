from facepy import GraphAPI

import random
import os
import re
import kinobot_utils.comments as check_comments
import kinobot_utils.subs as subs
import kinobot_utils.random_picks as random_picks
import normal_kino
import sys
import json
import datetime


FACEBOOK = os.environ.get("FACEBOOK")
FILM_COLLECTION = os.environ.get("FILM_COLLECTION")
TV_COLLECTION = os.environ.get("TV_COLLECTION")
MOVIE_JSON = os.environ.get("MOVIE_JSON")
TV_JSON = os.environ.get("TV_JSON")
COMMENTS_JSON = os.environ.get("COMMENTS_JSON")
MONKEY_PATH = os.environ.get("MONKEY_PATH")
FB = GraphAPI(FACEBOOK)

tiempo = datetime.datetime.now()
tiempo_str = tiempo.strftime("Automatically executed at %H:%M:%S GMT-4")


def get_monkey():
    monkey = random.choice(os.listdir(MONKEY_PATH))
    return MONKEY_PATH + monkey


def get_normal():
    id_normal = normal_kino.main(FILM_COLLECTION, TV_COLLECTION, FB, tiempo_str)
    comment_post(id_normal)


def cleansub(text):
    cleanr = re.compile("<.*?>")
    cleantext = re.sub(cleanr, "", text)
    return cleantext


def post_multiple(images, message):
    print(images)
    IDs = []
    for image in images:
        IDs.append(
            {
                "media_fbid": FB.post(
                    path="me/photos", source=open(image, "rb"), published=False
                )["id"]
            }
        )
    final = FB.post(
        path="me/feed",
        attached_media=json.dumps(IDs),
        message=message,
        published=False,
    )
    return final["id"]


def post_request(file, movie_info, discriminator, request, tiempo, is_episode=False, is_multiple=False):
    if is_episode:
        title = "{} - {}{}".format(
            movie_info["title"], movie_info["season"], movie_info["episode"]
        )
    else:
        title = "{} by {}".format(movie_info["title"], movie_info["director(s)"])

    print("Posting")
    disc = cleansub(discriminator)
    mes = (
        "{}\n{}\n\nRequested by {} (!req {})\n\n"
        "{}\nThis bot is open source: https://github.com/"
        "vitiko98/Certified-Kino-Bot".format(
            title, disc, request["user"], request["comment"], tiempo_str
        )
    )
    if is_multiple:
        return post_multiple(file, mes)
    else:
        id2 = FB.post(
            path="me/photos", source=open(file, "rb"), published=False, message=mes
        )
        return id2["id"]


def comment_post(postid):
    desc = random_picks.get_rec(MOVIE_JSON)
    desc.save("/tmp/tmp_collage.png")
    com = (
        "Complete list: https://kino.caretas.club\n\nRequest examples:\n"
        '"!req Taxi Driver [you talking to me?]"\n"!req Stalker [20:34]"\n'
        '"!req The Wire s01e01 [this america, man] [40:30]"'
    )
    FB.post(
        path=postid + "/comments",
        source=open("/tmp/tmp_collage.png", "rb"),
        message=com,
    )
    print(postid)


def notify(comment_id, content, fail=False):
    monkey = get_monkey()
    if not fail:
        noti = (
            "202: Your request was successfully executed."
            "\n\nI haven't added over 450 movies in vain! If you "
            "request the SAME MOVIE too many times, your requests will be disabled."
            " Check the list of available films"
            " and episodes: https://kino.caretas.club".format(content)
        )
    else:
        noti = (
            "404: Something went wrong with your request. Please, don't forget "
            "to check the list of available films, episodes and instructions befo"
            "re embarrassing the bot: https://kino.caretas.club"
        )
    FB.post(path=comment_id + "/comments", source=open(monkey, "rb"), message=noti)


def write_js(slctd):
    with open(COMMENTS_JSON, "w") as c:
        json.dump(slctd, c)


def handle_requests(slctd):
    inc = 0
    while True:
        m = slctd[inc]
        if not m["used"]:
            m["used"] = True
            print("Request: " + m["movie"])
            try:
                is_episode = True if m["episode"] else False
                Frames = []
                for frame in m["content"]:
                    Frames.append(
                        subs.Subs(
                            m["movie"],
                            frame,
                            MOVIE_JSON,
                            TV_JSON,
                            is_episode=is_episode,
                        )
                    )

                if len(Frames) > 1:
                    names = random.sample(range(1000, 2000), len(Frames))
                    outputs = ["/tmp/" + str(name) + ".png" for name in names]
                    quote_list = [word.discriminator for word in Frames]
                    if Frames[0].isminute:
                        discriminator = "Minutes: " + ", ".join(quote_list)
                    else:
                        discriminator = ", ".join(quote_list)
                    print("Getting png...")
                    for n in range(len(Frames)):
                        Frames[n].pill.save(outputs[n])
                    post_id = post_request(
                        outputs,
                        Frames[0].movie,
                        discriminator,
                        m,
                        tiempo,
                        is_episode,
                        True,
                    )
                else:
                    output = "/tmp/" + m["id"] + ".png"
                    Frames[0].pill.save(output)
                    if Frames[0].isminute:
                        discriminator = "Minute: " + Frames[0].discriminator
                    else:
                        discriminator = Frames[0].discriminator
                    post_id = post_request(
                        output,
                        Frames[0].movie,
                        discriminator,
                        m,
                        tiempo,
                        is_episode,
                    )

                write_js(slctd)
                comment_post(post_id)
                notify(m['id'], m['comment'])
                break
            except (TypeError, NameError, cv2.error, AttributeError):
                notify(m['id'], m['comment'], fail=True)
                write_js(slctd)
                pass

        inc += 1
        if inc == len(slctd):
            get_normal()
            break


def main():
    slctd = check_comments.main(COMMENTS_JSON, FB)
    print(slctd)
    if slctd:
        handle_requests(slctd)
    else:
        get_normal()


if __name__ == "__main__":
    sys.exit(main())