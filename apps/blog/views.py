from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework_api.views import StandardAPIView
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import NotFound, APIException, ValidationError
from django.db.models import Q, F, Prefetch
from django.shortcuts import get_object_or_404
import redis
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache

from .models import (
    Post, 
    Heading, 
    PostAnalytics, 
    Category, 
    CategoryAnalytics, 
    PostInteraction, 
    Comment,
    PostLike,
    PostShare,
)
from .serializers import (
    PostListSerializer, 
    PostSerializer, 
    HeadingSerializer, 
    PostView, 
    CategoryListSerializer,
    CommentSerializer,
)
from .utils import get_client_ip
from utils.string_utils import sanitize_string, sanitize_html
from .tasks import increment_post_impressions
from core.permissions import HasValidAPIKey
from .tasks import increment_post_views_task
from apps.authentication.models import UserAccount
from apps.mymedia.models import MyMedia

from faker import Faker
import random
import uuid
from django.utils.text import slugify

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)

"""class PostListView(ListAPIView):
    queryset = Post.postobjects.all()
    serializer_class = PostListSerializer"""

class PostAuthorViews(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def get(self, request):
        """
        List an author's posts
        """

        user = request.user
        if user.role == 'customer':
            return self.error("You do not have permission to create posts")

        posts = Post.objects.filter(user=user)

        if not posts.exists():
            raise NotFound(detail="No posts found.")

        serialized_posts = PostListSerializer(posts, many=True).data

        return self.paginate(request, serialized_posts)

    def post(self, request):
        """
        Create a post for an author
        """

        # Validate user role
        user = request.user
        if user.role == "customer":
            return self.error("You do not have permission to create posts")

        # Validate required fields
        required_fields = ["title", "content", "slug", "category"]
        missing_fields = [
            field for field in required_fields if not request.data.get(field)
        ]
        if missing_fields:
            return self.error(f"Missing required fields: {', '.join(missing_fields)}")

        # Get params
        title = sanitize_string(request.data.get('title', None))
        description = sanitize_string(request.data.get('description', ""))
        content = sanitize_html(request.data.get('content', None))

        # Thumbnail params
        thumbnail_name = request.data.get("thumbnail_name", None)
        thumbnail_size = request.data.get("thumbnail_size", None)
        thumbnail_type = request.data.get("thumbnail_type", None)
        thumbnail_key = request.data.get("thumbnail_key", None)
        thumbnail_order = request.data.get("thumbnail_order", 0)
        thumbnail_media_type = request.data.get("thumbnail_media_type", 'image')

        # Extra params
        keywords = sanitize_string(request.data.get("keywords", ""))
        slug = slugify(request.data.get("slug", None))
        category_slug = slugify(request.data.get("category", None))

        # Validate the existence of the category
        try:
            category = Category.objects.get(slug=category_slug)
        except Category.DoesNotExist:
            return self.error(
                f"Category '{category_slug}' does not exist.", status=400
            )

        try:
            post = Post.objects.create(
                user=user,
                title=title,
                description=description,
                content=content,
                keywords=keywords,
                slug=slug,
                category=category,
            )

            if thumbnail_key:
                thumbnail = Media.objects.create(
                    order=thumbnail_order,
                    name=thumbnail_name,
                    size=thumbnail_size,
                    type=thumbnail_type,
                    key=thumbnail_key,
                    media_type=thumbnail_media_type
                )

                post.thumbnail = thumbnail
                post.save()

            # Creating headings
            headings = request.data.get("headings", [])
            for heading_data in headings:
                Heading.objects.create(
                    post=post,
                    title=heading_data.get("title"),
                    slug=heading_data.get("slug"),
                    level=heading_data.get("level"),
                    order=heading_data.get("order")
                )

        except Exception as e:
            return self.error(f"An error occurred: {str(e)}")
        
        return self.response(
            f"Post '{post.title}' created successfully. It will be showed in a few minutes",
            status=status.HTTP_201_CREATED
        )

    def put(self, request):
        """
        Update a post for an author
        """

        # Get user
        user = request.user
        if user.role == 'customer':
            return self.error("You do not have permission to edit posts")

        post_slug = request.data.get("post_slug", None)
        if not post_slug:
            raise NotFound(detail="Post slug must be provided")

        try:
            post = Post.objects.get(slug=post_slug, user=user)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post {post_slug} does not exist")

        # Get params 
        title = sanitize_string(request.data.get('title', None))
        description = sanitize_string(request.data.get('description', None))
        content = sanitize_html(request.data.get('content', None))
        category_slug = slugify(request.data.get("category", post.category.slug))
        post_status = sanitize_string(request.data.get('status', 'draft'))

        # Thumbnail params
        thumbnail_name = request.data.get("thumbnail_name", None)
        thumbnail_size = request.data.get("thumbnail_size", None)
        thumbnail_type = request.data.get("thumbnail_type", None)
        thumbnail_key = request.data.get("thumbnail_key", None)
        thumbnail_order = request.data.get("thumbnail_order", 0)
        thumbnail_media_type = request.data.get("thumbnail_media_type", 'image')
        
        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug)
            except Category.DoesNotExist:
                return self.error(
                    f"Category '{category_slug}' does not exist.", status=400
                )
            post.category = category

        if title:
            post.title = title

        if description:
            post.description = description

        if content:
            post.content = content

        if thumbnail_key:
            thumbnail = Media.objects.create(
                order=thumbnail_order,
                name=thumbnail_name,
                size=thumbnail_size,
                type=thumbnail_type,
                key=thumbnail_key,
                media_type=thumbnail_media_type
            )
            post.thumbnail = thumbnail

        post.status = post_status

        # Updating headings
        headings = request.data.get("headings", [])
        if headings:
            post.headings.all().delete()  # Remove existing headings
            for heading_data in headings:
                Heading.objects.create(
                    post=post,
                    title=heading_data.get("title"),
                    level=heading_data.get("level"),
                    order=heading_data.get("order")
                )

        post.save()

        return self.response(f"Post {post.title} updated successfully. Changes will be reflected in a few minutes.")

    def delete(self, request):
        """
        Delete a post for an author
        """

        user = request.user
        if user.role == 'customer':
            return self.error("You do not have permission to create posts")
        
        post_slug = request.query_params.get("slug", None)
        if not post_slug:
            raise NotFound(detail="Post slug must be provided.")
        
        try:
            post = Post.objects.get(slug=post_slug, user=user)
        except Post.DoesNotExist:
            raise NotFound(f"Post {post_slug} does not exist.")
        
        post.delete()
        
        return self.response(f"Post with slug {post_slug} deleted successully.")

class PostListView(StandardAPIView): # APIWiew allows us to have more control over our views
    permission_classes = [HasValidAPIKey]

    # @method_decorator(cache_page(60 * 1)) Not recommended when you have a complex logic
    def get(self, request, *args, **kwargs):
        try:
            # Request parameters
            search = request.query_params.get("search", "").strip()
            sorting = request.query_params.get("sorting", None)
            author = request.query_params.get("author", None)
            ordering = request.query_params.get("ordering", None)
            categories = request.query_params.getlist("category", [])
            page = request.query_params.get("p", "1")


            cache_key = f"post_list:{search}:{sorting}:{ordering}:{author}:{categories}:{page}"

            # Checking if the data is in cache
            cached_posts = cache.get(cache_key)
            if cached_posts:
                for post in cached_posts:
                    redis_client.incr(f"post:impressions:{post['id']}")
                return self.paginate(request, cached_posts)
            
            # Initial query empty
            posts = Post.postobjects.all().select_related("category").prefetch_related(
                Prefetch("post_analytics", to_attr="analytics_cache")
            )

            if not posts.exists():
                raise NotFound(detail="No posts found")

            # Getting post from database if data is not in cache
            # Filter by search
            if search != "":
                posts = posts.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(content__icontains=search) |
                    Q(keywords__icontains=search)
                )
            
            # Filter by author
            if author:
                posts = posts.filter(user__username=author)

            # Applying filter by Category
            if categories:
                category_queries = Q()
                for category in categories:
                    # Checking if category is a valid uuid
                    try:
                        uuid.UUID(category)
                        uuid_query = (
                            Q(category__id=category)
                        )
                        category_queries |= uuid_query # Logical union
                    except ValueError:
                        slug_query = (
                            Q(category__slug=category)
                        )
                        category_queries |= slug_query
                posts = posts.filter(category_queries).distinct()
            
            # Applying sorting if provided
            if sorting:
                if sorting == "newest":
                    posts = posts.order_by("-created_at")
                elif sorting == "recently_updated":
                    posts = posts.order_by("-updated_at")
                elif sorting == "most_viewed":
                    posts = posts.annotate(popularity=F("analytics_cache__views")).order_by("-popularity")

            # Filter by order
            if ordering:
                if ordering == "az":
                    posts = posts.order_by("title")
                if ordering == "za":
                    posts = posts.order_by("-title")

            # Serializing data before saving in cache
            serialized_posts = PostListSerializer(posts, many=True).data
            cache.set(cache_key, serialized_posts, timeout=60 * 5)

            # Increasing impressions in Redis
            for post in posts:
                # increment_post_impressions.delay(post.id)
                redis_client.incr(f"post:impressions:{post.id}")
                
            return self.paginate(request, serialized_posts) 

        except Post.DoesNotExist:
            raise NotFound(detail="No posts found")
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")

class PostDetailView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        ip_address = get_client_ip(request)
        slug = request.query_params.get("slug")
        user = request.user if request.user.is_authenticated else None

        if not slug:
            raise NotFound(detail="A valid slug must be provided")

        try:
            # Checking if the data is in cache
            # cached_post = cache.get(f"post_detail:{slug}")
            # if cached_post:
            #     # increment_post_views_task.delay(cached_post["slug"], ip_address)
            #     self._register_view_interaction(cached_post["slug"], ip_address, user)
            #     return self.response(cached_post)

            cache_key = f"post_detail:{slug}"
            cached_post = cache.get(cache_key)
            if cached_post:
                serialized_post = PostSerializer(cached_post, context={'request': request}).data
                self._register_view_interaction(cached_post, ip_address, user)
                return self.response(serialized_post)

            # If data is not in cahce, get data from database
            try:
                post = Post.postobjects.get(slug=slug)
            except Post.DoesNotExist:
                raise NotFound(f"Post with slug '{slug}' does not exist")

            serialized_post = PostSerializer(post, context={"request": request}).data

            # Saving data in cache
            cache.set(cache_key, post, timeout=60 * 5)

            # increment_post_views_task.delay(post.slug, ip_address)
            # Register interaction
            self._register_view_interaction(post, ip_address, user)

        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")

        return self.response(serialized_post)

    def _register_view_interaction(self, post, ip_address, user):
        """
        It records 'view' type interactions, handles increments of unique and total views, and updates PostAnalytics.
        """

        # If 'post' is a string (slug), get the Post object
        if isinstance(post, str):
            post = Post.postobjects.get(slug=post)

        # Check if this IP and user have already logged a single view
        if not PostView.objects.filter(post=post, ip_address=ip_address, user=user).exists():
            # Create a single-view record
            PostView.objects.create(post=post, ip_address=ip_address, user=user)

            try:
                PostInteraction.objects.create(
                    user=user,
                    post=post,
                    interaction_type="view",
                    ip_address=ip_address,
                )
            except Exception as e:
                raise ValueError(f"An error ocurred while creating PostInteraction: {str(e)}")
            # Increment the view count in PostAnalytics
            analytics, _ = PostAnalytics.objects.get_or_create(post=post)
            analytics.increment_metric("views")

class PostHeadingsView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        post_slug = request.query_params.get("slug")
        heading_objects = Heading.objects.filter(post__slug = post_slug)
        serialized_data = HeadingSerializer(heading_objects, many=True).data
        return self.response(serialized_data)

    """serializer_class = HeadingSerializer
    
    def get_queryset(self):
        post_slug = self.kwargs.get("slug")
        return Heading.objects.filter(post__slug=post_slug)"""

class IncrementPostClickView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    permission_classes = [permissions.AllowAny]
    def post(self, request):
        """Increment the click counter of a post based on a slug"""
        data = request.data
        try:
            post = Post.postobjects.get(slug=data["slug"])
        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")
        
        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics")

        return self.response({
            "message": "Click incremented successfully",
            "clicks": post_analytics.clicks
        })

class CategoryListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        try:
            parent_slug = request.query_params.get("parent_slug", None)
            ordering = request.query_params.get("ordering", None)
            sorting = request.query_params.get("sorting", None)
            search = request.query_params.get("search", "").strip()
            page = request.query_params.get("p", "1")

            # Checking if the data is in cache
            cache_key = f"category_list:{page}:{ordering}:{sorting}:{search}:{parent_slug}"
            cached_categories = cache.get(cache_key)
            if cached_categories:
                # NO serialices de nuevo ni uses métodos del serializer aquí
                for category in cached_categories:
                    redis_client.incr(f"category:impressions:{category['id']}")
                return self.paginate(request, cached_categories)

            # Initial query empty
            if parent_slug:
                categories = Category.objects.filter(parent__slug=parent_slug).prefetch_related(
                    Prefetch("category_analytics", to_attr="analytics_cache")
                )
            else:
                # If we don't spicify a parent id we will search for a parent category
                categories = Category.objects.filter(parent__isnull=True).prefetch_related(
                    Prefetch("category_analytics", to_attr="analytics_cache")
                )

            if not categories.exists():
                raise NotFound(detail="No categories found")

            # Getting post from database if data is not in cache
            # Filter by search
            if search != "":
                categories = categories.filter(
                    Q(name__icontains=search) |
                    Q(slug__icontains=search) |
                    Q(title__icontains=search) |
                    Q(description__icontains=search) 
                )

            # Applying sorting if provided
            if sorting:
                if sorting == "newest":
                    categories = categories.order_by("-created_at")
                elif sorting == "recently_updated":
                    categories = categories.order_by("-updated_at")
                elif sorting == "most_viewed":
                    categories = categories.annotate(popularity=F("analytics_cache__views")).order_by("-popularity")

            # Filter by order
            if ordering:
                if ordering == "az":
                    posts = posts.order_by("name")
                if ordering == "za":
                    posts = posts.order_by("-name")

            # Serialization
            serialized_categories = CategoryListSerializer(categories, many=True).data

            # Saving serialized data in cache
            cache.set(cache_key, serialized_categories, timeout=60 * 5)

            # Increasing impressions in Redis
            for category in serialized_categories:
                if 'id' in category:
                    redis_client.incr(f"category:impressions:{category['id']}")

            return self.paginate(request, serialized_categories)
        
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")

class CategoryDetailView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        try:
            # Params
            slug = request.query_params.get("slug", None)
            page = request.query_params.get("p", "1")

            if not slug:
                return self.error("Missing slug parameter") # Bad Request (400)
            
            # Build cache
            cache_key = f"category_posts:{slug}:{page}"
            # Checking if the data is in cache
            cached_posts = cache.get(cache_key)
            if cached_posts:
                
                for post in cached_posts:
                    redis_client.incr(f"post:impressions:{post['id']}")
                return self.paginate(request, cached_posts)

            # Getting category by slug
            category = get_object_or_404(Category, slug=slug)

            # Get all the pots belonging to a category
            posts = Post.postobjects.filter(category=category).select_related("category").prefetch_related(
                    Prefetch("post_analytics", to_attr="analytics_cache")
                )
            
            if not posts.exists():
                raise NotFound(detail=f"No posts found for category '{category.name}'")
            
            # Serializa antes de guardar en caché
            serialized_posts = PostListSerializer(posts, many=True).data
            cache.set(cache_key, serialized_posts, timeout=60 * 5)
            
            # Serializing the posts
            serialized_posts = PostListSerializer(posts, many=True).data

            # Increasing impressions in Redis
            for post in posts:
                # increment_post_impressions.delay(post.id)
                redis_client.incr(f"post:impressions:{post.id}")

            return self.paginate(request, serialized_posts)

        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")

class IncrementCategoryClickView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    permission_classes = [permissions.AllowAny]
    def post(self, request):
        """Increment the click counter of a category based on a slug"""
        data = request.data
        try:
            category = Category.objects.get(slug=data["slug"])
        except Category.DoesNotExist:
            raise NotFound(detail="The requested category does not exist")
        
        try:
            category_analytics, created = CategoryAnalytics.objects.get_or_create(category=category)
            category_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating category analytics")

        return self.response({
            "message": "Click incremented successfully",
            "clicks": category_analytics.clicks
        })

class ListPostCommentsViews(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        """
        List the comments on a post
        """

        post_slug = request.query_params.get("slug", None)
        page = request.query_params.get("p", "1")

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")

        # Define cache key
        cache_key = f"post_comments:{post_slug}:{page}"
        cached_comments = cache.get(cache_key)
        if cached_comments:
            return self.paginate(request, cached_comments)

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise ValueError(f"Post with slug '{post_slug}' does not exist")

        # Get the main comments
        comments = Comment.objects.filter(post=post, parent=None)
        serialized_comments = CommentSerializer(comments, many=True).data

        # Save key in index
        cache_index_key = f"post_comments_cache_keys:{post_slug}"
        cache_keys = cache.get(cache_index_key, [])
        cache_keys.append(cache_key)
        cache.set(cache_index_key, cache_keys, timeout=60 * 5)

        # Store the data in cache (For five minutes)
        cache.set(cache_key, serialized_comments, timeout=60 * 5)

        return self.paginate(request, serialized_comments)

class PostCommentsViews(StandardAPIView):
    permissions_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):
        """
        Create a new comment for a post
        """
        
        # Get parameters
        post_slug = request.data.get("slug", None)
        user = request.user
        ip_address = get_client_ip(request)
        content = sanitize_html(request.data.get("content", None))

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post with slug '{post_slug}' does not exist")

        # Create the comment
        comment = Comment.objects.create(
            user=user,
            post=post,
            content=content,
        )
        # serialized_comment = CommentSerializer(comment).data

        # Invalidate the comment cache for posts
        # cache_key = f"post_comments:{post_slug}:*"
        self._invalidate_post_comments_cache(post_slug)

        # Update interacion posts
        # return self.response(serialized_comment)
        self._register_comment_interaction(comment, post, ip_address, user)

        return self.response(f"Comment created for post {post.title}")

    def put(self, request):
        """
        Update an existing comment for a post
        """

        # Get parameters
        comment_id = request.data.get("comment_id", None)
        user = request.user
        content = sanitize_html(request.data.get("content", None))

        if not comment_id:
            raise NotFound(detail="A valid comment ID must be provided")

        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with ID '{comment_id}' does not exist")

        # Update the comment
        comment.content = content
        comment.save()

        # Invalidate the comment cache for posts
        self._invalidate_post_comments_cache(comment.post.slug)

        if  comment.parent and comment.parent.replies.exists():
            self._invalidate_comment_replies_cache(comment.parent.id)

        return self.response("Comment content updated successfully")

    def delete(self, request):
        """
        Delete an existing comment for a post
        """

        # Get parameters
        comment_id = request.query_params.get("comment_id", None)

        if not comment_id:
            raise NotFound(detail="A valid comment ID must be provided")

        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with ID '{comment_id}' does not exist")

        post = comment.post
        post_analytics, _ = PostAnalytics.objects.get_or_create(post=post)

        if  comment.parent and comment.parent.replies.exists():
            self._invalidate_comment_replies_cache(comment.parent.id)

        comment.delete()

        # Update metrics
        commnets_count = Comment.objects.filter(post=post, is_active=True).count()
        post_analytics.comments = commnets_count
        post_analytics.save()

        # Invalidate the comment cache for posts
        self._invalidate_post_comments_cache(post.slug)

        return self.response("Comment deleted successfully")

    def _register_comment_interaction(self, comment, post, ip_address, user):
        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type="comment",
            comment=comment,
            ip_address=ip_address,
        )
        # Increment the comment count in PostAnalytics
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric("comments")

    def _invalidate_post_comments_cache(self, post_slug):
        """
        Invalidate all cache entries for a post's comments.

        Instead of relying on a stored index of page-specific keys (which may
        be incomplete if a page was never accessed or the index expired), we
        perform a wildcard deletion against Redis. If the cache backend
        supports ``delete_pattern`` (django-redis) we use that; otherwise we
        fall back to querying the redis client directly.
        """
        pattern = f"post_comments:{post_slug}:*"

        # try to use the high-level cache API first
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            # fallback to raw redis if delete_pattern is unavailable
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)

        # clear any index we might still maintain (optional)
        cache_index_key = f"post_comments_cache_keys:{post_slug}"
        cache.delete(cache_index_key)

    def _invalidate_comment_replies_cache(self, comment_id):
        """
        Invalidate all cache entries for replies to a given comment using a
        wildcard pattern. This mirrors the implementation used in the
        ``PostCommentsViews`` helper so that updates/removals take effect
        immediately regardless of which page clients have cached.
        """
        pattern = f"comment_replies:{comment_id}:*"
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)

        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache.delete(cache_index_key)

class ListCommentRepliesView(StandardAPIView):
    permissions_classes = [HasValidAPIKey]

    def get(self, request):

        comment_id = request.query_params.get("comment_id")
        page = request.query_params.get("p", "1")

        if not comment_id:
            raise NotFound(detail="A valid comment ID must be provided")

        # Define cache key
        cache_key = f"comment_replies:{comment_id}:{page}"
        cached_replies = cache.get(cache_key)

        if cached_replies:
            return self.paginate(request, cached_replies)

        # Get the parent comment
        try:
            parent_comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with ID '{comment_id}' does not exist")

        # Filter active replies from the parent comment
        replies = parent_comment.replies.filter(is_active=True).order_by("-created_at")

        # Serialize response
        serialized_replies = CommentSerializer(replies, many=True).data

        # Register the key in the cache index
        self._register_comment_reply_cache_key(comment_id, page)

        # Save the answers to the cache
        cache.set(cache_key, serialized_replies)

        return self.paginate(request, serialized_replies)

    def _register_comment_reply_cache_key(self, comment_id, cache_key):
        """
        Register cache keys related to comments
        """
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])
        if cache_key not in cache_keys:
            cache_keys.append(cache_key)
        cache.set(cache_index_key, cache_keys, timeout=60 * 5)

class CommentReplyViews(StandardAPIView):
    permissions_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):
        """
        Create a new reply to a comment
        """

        # Get parameters
        comment_id = request.data.get("comment_id", None)
        user = request.user
        ip_address = get_client_ip(request)
        content = sanitize_html(request.data.get("content", None))

        if not comment_id:
            raise NotFound(detail="A valid comment ID must be provided")

        # Get the parent comment
        try:
            parent_comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with ID '{comment_id}' does not exist")

        # Create Reply
        comment = Comment.objects.create(
            user=user,
            post=parent_comment.post,
            parent=parent_comment,
            content=content,
        )

        # Invalidate the response cache
        self._invalidate_comment_replies_cache(comment_id)

        # Update metrics
        self._register_comment_interaction(comment, comment.post, ip_address, user)

        return self.response("Comment reply created successfully")

    def _register_comment_interaction(self, comment, post, ip_address, user):
        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type="comment",
            comment=comment,
            ip_address=ip_address,
        )
        # Increment the comment count in PostAnalytics
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric("comments")

    def _invalidate_comment_replies_cache(self, comment_id):
        """
        Invalidate all cache entries for replies to a given comment using a
        wildcard pattern. This mirrors the implementation used in the
        ``PostCommentsViews`` helper so that updates/removals take effect
        immediately regardless of which page clients have cached.
        """
        pattern = f"comment_replies:{comment_id}:*"
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)

        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache.delete(cache_index_key)

class PostLikeViews(StandardAPIView):
    permissions_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):
        """
        Create a new like for a post
        """

        post_slug = request.data.get("slug", None)
        user = request.user

        ip_address = get_client_ip(request)

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")

        # Check if the user has already liked the post
        if PostLike.objects.filter(post=post, user=user).exists():
            raise ValidationError(detail="You have already liked this post.")

        # Create the 'like'
        PostLike.objects.create(post=post, user=user)

        # Record interaction 
        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type="like",
            ip_address=ip_address
        )

        # Increase metrics
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric("likes")

        return self.response(f"You have liked the post: {post.title}")

    def delete(self, request):
        """
        Remove a 'like' from a post
        """
        post_slug = request.query_params.get("slug", None)
        user = request.user

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post with slug: {post_slug} does not exist")
        
        # Check if the user has liked the post
        try:
            like = PostLike.objects.get(post=post, user=user)
        except PostLike.DoesNotExist:
            raise ValidationError(detail="You have not liked this post.")
        
        # Remove the 'like'
        like.delete()

        # Update metrics
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.likes = PostLike.objects.filter(post=post).count()
        analytics.save()

        return self.response(f"You have unliked the post: {post.title}")

class PostShareView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """
        Manage the action of sharing a post.
        """
        # Obtain parameters
        post_slug = request.data.get("slug", None)
        platform = request.data.get("platform", "other").lower()
        user = request.user if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")
        
        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")

        # Verify that the platform is valid
        valid_platforms = [choice[0] for choice in PostShare._meta.get_field("platform").choices]
        if platform not in valid_platforms:
            raise ValidationError(detail=f"Invalid platform. Valid options are: {', '.join(valid_platforms)}")
        
        # Create a 'share' record
        PostShare.objects.create(
            post=post,
            user=user,
            platform=platform,
        )

        # Record interaction
        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type="share",
            ip_address=ip_address
        )

        # Update metrics
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric("shares")

        return self.response(f"Post '{post.title}' shared successfully on {platform.capitalize()}")

class GenerateFakePostsView(StandardAPIView):

    def get(self,request):
        # Configurar Faker
        fake = Faker()

        # Obtener todas las categorías existentes
        categories = list(Category.objects.all())

        if not categories:
            return self.response("No hay categorías disponibles para asignar a los posts", 400)

        posts_to_generate = 50  # Number of fake post to create
        status_options = ["draft", "published"]

        for _ in range(posts_to_generate):
            title = fake.sentence(nb_words=6)  # To generate a random title
            user = UserAccount.objects.get(username="test_editor")
            post = Post(
                id=uuid.uuid4(),
                user=user,
                title=title,
                description=fake.sentence(nb_words=12),
                content=fake.paragraph(nb_sentences=5),
                keywords=", ".join(fake.words(nb=5)),
                slug=slugify(title),  # To generate a slug from an title
                category=random.choice(categories),  # Assign a random gategory
                status=random.choice(status_options),
            )
            post.save()

        return self.response(f"{posts_to_generate} posts generados exitosamente.")

class GenerateFakeAnalyticsView(StandardAPIView):

    def get(self, request):
        fake = Faker()

        # Get all existing posts
        posts = Post.objects.all()

        if not posts:
            return self.response({"error": "No hay posts disponibles para generar analíticas"}, status=400)

        analytics_to_generate = len(posts)  # One analysis per post
        # Generar analíticas para cada post
        for post in posts:
            views = random.randint(50, 1000)  # Random number of views
            impressions = views + random.randint(100, 2000)  # Impressions >= views
            clicks = random.randint(0, views)  # Clicks are <= views
            avg_time_on_page = round(random.uniform(10, 300), 2)  # Average time in seconds
            
            # Create or update analytics for the post
            analytics, created = PostAnalytics.objects.get_or_create(post=post)
            analytics.views = views
            analytics.impressions = impressions
            analytics.clicks = clicks
            analytics.avg_time_on_page = avg_time_on_page
            analytics._update_click_through_rate()  # Recalculate the CTR
            analytics.save()

        return self.response({"message": f"Analíticas generadas para {analytics_to_generate} posts."})
