"""[Post-MVP] Social features — ratings, reviews, comments, communities."""

import json

import click

from ..api_client import api_client


@click.group()
def social():
    """[Post-MVP] Social features — ratings, reviews, comments, communities."""


@social.group("ratings")
def social_ratings():
    """Asset ratings."""


@social_ratings.command("list")
@click.option("--asset-id", default=None)
def social_ratings_list(asset_id):
    url = "social/ratings/"
    if asset_id:
        url += f"?asset_id={asset_id}"
    data = api_client.get(url)
    click.echo(json.dumps(data, indent=2))


@social_ratings.command("create")
@click.option("--asset-id", required=True)
@click.option("--score", type=click.IntRange(1, 5), required=True)
def social_ratings_create(asset_id, score):
    resp = api_client.post("social/ratings/", json={"asset_id": asset_id, "score": score})
    click.echo(json.dumps(resp, indent=2))


@social.group("reviews")
def social_reviews():
    """Asset reviews."""


@social_reviews.command("list")
@click.option("--asset-id", default=None)
def social_reviews_list(asset_id):
    url = "social/reviews/"
    if asset_id:
        url += f"?asset_id={asset_id}"
    data = api_client.get(url)
    click.echo(json.dumps(data, indent=2))


@social_reviews.command("create")
@click.option("--asset-id", required=True)
@click.option("--title", required=True)
@click.option("--body", required=True)
@click.option("--rating", type=click.IntRange(1, 5), required=True)
def social_reviews_create(asset_id, title, body, rating):
    resp = api_client.post(
        "social/reviews/",
        json={
            "asset_id": asset_id,
            "title": title,
            "body": body,
            "rating": rating,
        },
    )
    click.echo(json.dumps(resp, indent=2))


@social.group("comments")
def social_comments():
    """Comments on assets."""


@social_comments.command("list")
@click.option("--asset-id", default=None)
def social_comments_list(asset_id):
    url = "social/comments/"
    if asset_id:
        url += f"?asset_id={asset_id}"
    data = api_client.get(url)
    click.echo(json.dumps(data, indent=2))


@social_comments.command("create")
@click.option("--asset-id", required=True)
@click.option("--body", required=True)
def social_comments_create(asset_id, body):
    resp = api_client.post("social/comments/", json={"asset_id": asset_id, "body": body})
    click.echo(json.dumps(resp, indent=2))


@social.group("communities")
def social_communities():
    """Community management."""


@social_communities.command("list")
def social_communities_list():
    data = api_client.get("social/communities/")
    click.echo(json.dumps(data, indent=2))


@social_communities.command("create")
@click.option("--name", required=True)
@click.option("--description", default="")
def social_communities_create(name, description):
    resp = api_client.post("social/communities/", json={"name": name, "description": description})
    click.echo(json.dumps(resp, indent=2))
