import pytest
from app.services.ingestion.external_detector import detect_external_services

def test_requests_call():
    code = "import requests\nresp = requests.post('https://api.stripe.com', data={})"
    services = detect_external_services(code)
    assert len(services) == 1
    assert services[0]["service"] == "requests"
    assert services[0]["method"] == "post"
    assert services[0]["url"] == "https://api.stripe.com"

def test_boto3_call():
    code = "import boto3\ns3 = boto3.client('s3')"
    services = detect_external_services(code)
    assert len(services) == 1
    assert services[0]["service"] == "boto3"
    assert services[0]["method"] == "client"
    assert services[0]["url"] == "s3"

def test_no_external_call():
    code = "def add(a, b): return a + b"
    assert detect_external_services(code) == []
