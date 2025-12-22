from rest_framework import serializers
from .models import Post, Category, Heading, PostView
from apps.mymedia.serializers import MyMediaSerializer

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"

class CategoryListSerializer(serializers.ModelSerializer):
    thumbnail = MyMediaSerializer()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "thumbnail"]

class HeadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Heading
        fields = [
            "title",
            "slug",
            "level",
            "order",
        ]

class PostViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostView
        fields = "__all__"

class PostSerializer(serializers.ModelSerializer):
    category = CategorySerializer() 
    headings = HeadingSerializer(many=True)
    view_count = serializers.SerializerMethodField()
    thumbnail = MyMediaSerializer()
    
    class Meta:
        model = Post
        fields = "__all__"

    def get_view_count(self, obj):
        return obj.post_analytics.views

class PostListSerializer(serializers.ModelSerializer):
    category = CategoryListSerializer() # To display the category name instead of the category id
    view_count = serializers.SerializerMethodField()
    thumbnail = MyMediaSerializer()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "description",
            "thumbnail",
            "slug",
            "category",
            "view_count",
        ]

    def get_view_count(self, obj):
        return obj.post_analytics.views if obj.post_analytics else 0
