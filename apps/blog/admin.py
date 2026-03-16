from django.contrib import admin

from.models import (Category, 
    Post, 
    Heading, 
    PostAnalytics, 
    CategoryAnalytics, 
    PostInteraction,
    Comment,
    PostLike,
    PostShare,
    PostView,
)
from apps.mymedia.models import MyMedia

# Register your models here.
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "parent", "slug", "thumbnail_preview")
    search_fields = ("name", "title", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("parent",)
    ordering = ("name",)
    readonly_fields = ("id",)
    # list_editable = ("title",) Don't use. This was enabled for demostration purposes only

@admin.register(CategoryAnalytics)
class CategoryAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "category__name",
        "views",
        "impressions",
        "clicks",
        "click_through_rate",
        "avg_time_on_page"
    )
    search_fields = ("category__name",)
    readonly_fields = (
        "category",
        "views",
        "impressions",
        "clicks",
        "click_through_rate",
        "avg_time_on_page"
    )

    def category_name(self, obj):
        return obj.category.name
    
    category_name.short_description = "Category Name"

# Inline form 
# https://medium.com/django-unleashed/mastering-django-inline-admin-tabularinline-and-stackedinline-examples-c9f17accde84
# https://docs.djangoproject.com/en/5.2/ref/contrib/admin/#inlinemodeladmin-objects
class HeadingInLine(admin.TabularInline):
    model = Heading
    extra = 1
    fields = ("title", "level", "order", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):

    list_display = ("title", "status", "category", "created_at", "updated_at", "thumbnail_preview")
    search_fields = ("title", "description", "content", "keywords", "slug")
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ("status", "category", "updated_at")
    ordering = ("-created_at",) # Descending
    readonly_fields = ("id", "created_at", "updated_at")

    # To order the presentation of fields
    fieldsets = (
        ("General information", {
            "fields": ("title", "description", "content", "thumbnail", "keywords", "slug", "category", "user")
        }),
        ("Status & Dates", {
            "fields": ("status", "created_at", "updated_at")
        }),
    )

    inlines = [HeadingInLine]

"""@admin.register(Heading)
class HeadingAdmin(admin.ModelAdmin):
    list_display = ("title", 'post', "level", "order")
    search_fields = ("title", "post__title")
    list_filter = ("level", "post")
    ordering = ("post", "order")
    prepopulated_fields = {"slug": ("title",)}"""

@admin.register(PostAnalytics)
class PostAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "post__title",
        "views",
        "impressions",
        "clicks",
        "click_through_rate",
        "avg_time_on_page",
        "likes",
        "comments",
        "shares"
    )
    search_fields = ("post__title", "post__slug",)
    readonly_fields = (
        "post",
        "views",
        "impressions",
        "clicks",
        "click_through_rate",
        "avg_time_on_page",
        "likes",
        "comments",
        "shares"
    )

    def post_title(self, obj):
        return obj.post.title
    
    post_title.short_description = "Post Title"

@admin.register(PostInteraction)
class PostInteractionAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "interaction_type", "timestamp")
    search_fields = ("user__username", "post__title", "interaction_type")
    list_filter = ("interaction_type", "timestamp")
    ordering = ("-timestamp",)
    readonly_fields = ("id", "timestamp")

    def post_tile(self, obj):
        return obj.post.title
    
    post_tile.short_description = "Post Title"

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "parent", "created_at", "updated_at", "is_active")
    search_fields = ("user__username", "post__title", "content")
    list_filter = ("is_active", "created_at", "updated_at")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("user", "post", "parent")
    fieldsets = (
        ("General Information", {
            "fields": ("user", "post", "parent", "content")
        }),
        ("Status", {
            "fields": ("is_active", "created_at", "updated_at")
        }),
    )

@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "timestamp")
    search_fields = ("user__username", "post__title")
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)
    readonly_fields = ("id", "timestamp")
    list_select_related = ("user", "post")
    fieldsets = (
        ("General Information", {
            "fields": ("user", "post")
        }),
        ("Timestamp", {
            "fields": ("timestamp",)
        }),
    )

@admin.register(PostShare)
class PostShareAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "platform", "timestamp")
    search_fields = ("user__username", "post__title", "platform")
    list_filter = ("platform", "timestamp")
    ordering = ("-timestamp",)
    readonly_fields = ("id", "timestamp")
    list_select_related = ("user", "post")
    fieldsets = (
        ("General Information", {
            "fields": ("user", "post", "platform")
        }),
        ("Timestamp", {
            "fields": ("timestamp",)
        }),
    )


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "ip_address", "timestamp")
    search_fields = ("user__username", "post__title", "ip_address")
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)
    readonly_fields = ("id", "timestamp")
    list_select_related = ("user", "post")
    fieldsets = (
        ("General Information", {
            "fields": ("user", "post", "ip_address")
        }),
        ("Timestamp", {
            "fields": ("timestamp",)
        }),
    )

