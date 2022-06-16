import json
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import requests
from common.licenses import LicenseInfo
from common.loader import provider_details as prov
from common.storage.image import MockImageStore
from providers.provider_api_scripts.cleveland_museum import ClevelandDataIngester


_license_info = (
    "cc0",
    "1.0",
    "https://creativecommons.org/publicdomain/zero/1.0/",
    None,
)
license_info = LicenseInfo(*_license_info)

RESOURCES = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "resources/clevelandmuseum"
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s:  %(message)s", level=logging.DEBUG
)


class TestClevelandDataIngester(unittest.TestCase):
    def setUp(self):
        self.clm = ClevelandDataIngester()
        self.clm.media_stores = {
            "image": MockImageStore(
                provider=prov.CLEVELAND_DEFAULT_PROVIDER, license_info=license_info
            )
        }

    def _get_resource_json(self, json_name):
        with open(os.path.join(RESOURCES, json_name)) as f:
            resource_json = json.load(f)
        return resource_json

    def test_build_query_param_default(self):
        actual_param = self.clm.get_next_query_params({})
        expected_param = {"cc": "1", "has_image": "1", "limit": 1000, "skip": 0}
        assert actual_param == expected_param

    def test_build_query_param_increments_offset(self):
        previous_query_params = {"cc": "1", "has_image": "1", "limit": 1000, "skip": 0}

        actual_param = self.clm.get_next_query_params(previous_query_params)
        expected_param = {"cc": "1", "has_image": "1", "limit": 1000, "skip": 1000}
        assert actual_param == expected_param

    def test_get_image_type_web(self):
        image_data = self._get_resource_json("image_type_web.json")
        actual_url, actual_key = self.clm._get_image_type(image_data)
        expected_url = (
            "https://openaccess-cdn.clevelandart.org/1335.1917/1335.1917_web.jpg"
        )
        expected_key = "web"

        assert actual_url == expected_url
        assert actual_key == expected_key

    def test_get_image_type_print(self):
        image_data = self._get_resource_json("image_type_print.json")
        actual_url, actual_key = self.clm._get_image_type(image_data)
        expected_url = (
            "https://openaccess-cdn.clevelandart.org/" "1335.1917/1335.1917_print.jpg"
        )
        expected_key = "print"

        assert actual_url == expected_url
        assert actual_key == expected_key

    def test_get_image_type_full(self):
        image_data = self._get_resource_json("image_type_full.json")
        actual_url, actual_key = self.clm._get_image_type(image_data)
        expected_url = (
            "https://openaccess-cdn.clevelandart.org/" "1335.1917/1335.1917_full.tif"
        )
        expected_key = "full"

        assert actual_url == expected_url
        assert actual_key == expected_key

    def test_get_image_type_none(self):
        image_data = self._get_resource_json("image_type_none.json")
        actual_url, actual_key = self.clm._get_image_type(image_data)
        expected_url = None
        expected_key = None

        assert actual_url == expected_url
        assert actual_key == expected_key

    def test_get_metadata(self):
        data = self._get_resource_json("complete_data.json")
        actual_metadata = self.clm._get_metadata(data)
        expected_metadata = self._get_resource_json("expect_metadata.json")
        assert actual_metadata == expected_metadata

    def test_get_response_success(self):
        query_param = {"cc": 1, "has_image": 1, "limit": 1, "skip": 30000}
        response_json = self._get_resource_json("response_success.json")
        r = requests.Response()
        r.status_code = 200
        r.json = MagicMock(return_value=response_json)
        with patch.object(
            self.clm.delayed_requester, "get", return_value=r
        ) as mock_get:
            batch, _ = self.clm.get_batch(query_param)
        expected_response = self._get_resource_json("response_success.json")

        assert mock_get.call_count == 1
        assert response_json == expected_response
        assert len(batch) == 1

    def test_get_response_no_data(self):
        query_param = {"cc": 1, "has_image": 1, "limit": 1, "skip": 33000}
        response_json = self._get_resource_json("response_no_data.json")
        r = requests.Response()
        r.status_code = 200
        r.json = MagicMock(return_value=response_json)
        with patch.object(
            self.clm.delayed_requester, "get", return_value=r
        ) as mock_get:
            batch, should_continue = self.clm.get_batch(query_param)
        expected_response = self._get_resource_json("response_no_data.json")

        assert mock_get.call_count == 1
        assert response_json == expected_response
        assert len(batch) == 0

    def test_get_response_failure(self):
        query_param = {"cc": 1, "has_image": 1, "limit": 1, "skip": -1}
        r = requests.Response()
        r.status_code = 500
        r.json = MagicMock(return_value={"error": ""})
        with patch.object(
            self.clm.delayed_requester, "get", return_value=r
        ) as mock_get:
            self.clm.get_batch(query_param)

        assert mock_get.call_count == 4

    def test_get_response_None(self):
        query_param = {"cc": 1, "has_image": 1, "limit": 1, "skip": -1}
        with patch.object(
            self.clm.delayed_requester, "get", return_value=None
        ) as mock_get:
            batch, _ = self.clm.get_batch(query_param)

        assert batch is None
        assert mock_get.call_count == 4

    def test_handle_response(self):
        response_json = self._get_resource_json("handle_response_data.json")
        data = response_json["data"]
        actual_total_images = self.clm.process_batch(data)
        expected_total_images = 100

        assert actual_total_images == expected_total_images
