# Generated by Django 5.1.1 on 2024-09-21 00:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mod_shopify', '0003_orderaliexpressintegration'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShopifyAliexpressIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shopifyProductId', models.CharField(max_length=50)),
                ('aliexpressProductId', models.CharField(max_length=50)),
                ('aliexpressProductSku', models.CharField(max_length=70)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
