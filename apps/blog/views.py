from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework_api.views import StandardAPIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, APIException
from django.db.models import Q, F, Prefetch
from django.shortcuts import get_object_or_404
import redis
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache

from .models import Post, Heading, PostAnalytics, Category, CategoryAnalytics
from .serializers import PostListSerializer, PostSerializer, HeadingSerializer, PostView, CategoryListSerializer
from .utils import get_client_ip
from .tasks import increment_post_impressions
from core.permissions import HasValidAPIKey
from .tasks import increment_post_views_task

from faker import Faker
import random
import uuid
from django.utils.text import slugify

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)

"""class PostListView(ListAPIView):
    queryset = Post.postobjects.all()
    serializer_class = PostListSerializer"""

class PostListView(StandardAPIView): # APIWiew allows us to have more control over our views
    permission_classes = [HasValidAPIKey]

    # @method_decorator(cache_page(60 * 1)) Not recommended when you have a complex logic
    def get(self, request, *args, **kwargs):
        try:
            # Request parameters
            search = request.query_params.get("search", "").strip()
            sorting = request.query_params.get("sorting", None)
            ordering = request.query_params.get("ordering", None)
            categories = request.query_params.getlist("category", [])
            page = request.query_params.get("p", "1")


            cache_key = f"post_list:{search}:{sorting}:{ordering}:{categories}:{page}"

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

        try:
            # Checking if the data is in cache
            cached_post = cache.get(f"post_detail:{slug}")
            if cached_post:
                increment_post_views_task.delay(cached_post["slug"], ip_address)
                return self.response(cached_post)

            # If data is not in cahce, get data from database
            post = Post.postobjects.get(slug=slug)
            serialized_post = PostSerializer(post).data 

            # Saving data in cache
            cache.set(f"post_detail:{slug}", serialized_post, timeout=60 * 5)

            increment_post_views_task.delay(post.slug, ip_address)

        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")

        return self.response(serialized_post)

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
            post = Post(
                id=uuid.uuid4(),
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
