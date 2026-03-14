import pytest
from app.services.ingestion.orm_extractor import extract_orm_models

def test_sqlalchemy_model():
    code = """
from sqlalchemy import Column, Integer, String
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
"""
    models = extract_orm_models(code)
    assert len(models) == 1
    assert models[0]["name"] == "User"
    fields = {f["name"]: f["type"] for f in models[0]["fields"]}
    assert fields["id"] == "Column"
    assert fields["name"] == "Column"

def test_django_model():
    code = """
from django.db import models

class Product(models.Model):
    title = models.CharField(max_length=200)
    price = models.IntegerField()
"""
    models = extract_orm_models(code)
    assert len(models) == 1
    assert models[0]["name"] == "Product"
    fields = {f["name"]: f["type"] for f in models[0]["fields"]}
    assert fields["title"] == "CharField"
    assert fields["price"] == "IntegerField"

def test_not_a_model():
    code = "class Helper:\n    def do_work(self): pass"
    assert extract_orm_models(code) == []
