from celery import shared_task
import logging
import redis
from django.conf import settings

from .models import PostAnalytics, Post, CategoryAnalytics, Category

logger = logging.getLogger(__name__)
redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)

# NOTE: It's necessary to stop docker in the terminal and run it again after making changes on any tasks.py file to refresh the Celery Worker

# Task running with Celery
@shared_task
def increment_post_impressions(post_id):
    """Increment the impressions of the associated post"""
    try:
        analytics, created = PostAnalytics.objects.get_or_create(post__id=post_id)
        analytics.increment_impression()
    except Exception as e:
        logger.info(f"Error incrementing impressions for Post ID {post_id}: {str(e)}")

# Task running with Celery
@shared_task
def increment_post_views_task(slug, ip_address):
    """
    Increase views of a post
    """
    try:
        post = Post.objects.get(slug=slug)
        post_analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        post_analytics.increment_view(ip_address)
    except Exception as e:
        logger.info(f"Error incrementing views for Post Slug {slug}: {str(e)}")

# Task running with Celery Beat
@shared_task
def sync_impressions_to_db():
    """Sync the stored impressions on redis with the database"""
    keys = redis_client.keys("post:impressions:*")
    for key in keys:
        try:
            post_id = key.decode("utf-8").split(":")[-1]

            # Validate that the post exists
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                logger.info(f"Post with ID {post_id} does not exist. Skipping.")
                continue

            # Getting impressions from redis
            impressions = int(redis_client.get(key))
            if impressions == 0:
                redis_client.delete(key)
                continue
            
            # Get and create category analytics instance
            analytics, created = PostAnalytics.objects.get_or_create(post=post)

            # Increase impressions
            analytics.impressions += impressions
            analytics.save()

            # Update Click-Through Rate (CTR)
            analytics._update_click_through_rate()

            # Delete the Redis key after synchronization
            redis_client.delete(key)
        except Exception as e:
            logger.info(f"Error syncing impressions for  {key}: {str(e)}")

@shared_task
def sync_category_impressions_to_db():
    """Sync the stored impressions on redis with the database"""
    keys = redis_client.keys("category:impressions:*")
    for key in keys:
        try:
            # # Decode and extract the category ID from the Redis key
            category_id = key.decode("utf-8").split(":")[-1]

            # Validate that the category exists
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                logger.info(f"Category with ID {category_id} does not exist. Skipping.")
                continue
            
            # Getting impressions from redis
            impressions = int(redis_client.get(key))
            if impressions == 0:
                redis_client.delete(key)
                continue

            # Get and create category analytics instance
            analytics, created = CategoryAnalytics.objects.get_or_create(category=category)

            # Increase impressions
            analytics.impressions += impressions
            analytics.save()

            # Update Click-Through Rate (CTR)
            analytics._update_click_through_rate()

            # Delete the Redis key after synchronization
            redis_client.delete(key)
        except Exception as e:
            print(f"Error syncing impressions for {key}: {str(e)}")


