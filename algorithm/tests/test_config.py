import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import Config


class TestConfig(unittest.TestCase):
    def test_model_endpoint_bare_host_gets_port(self):
        cfg = Config(server_url="django")
        self.assertEqual(cfg.model_endpoint, "http://django:5000")

    def test_model_endpoint_full_url_preserved(self):
        cfg = Config(server_url="http://192.168.1.101:5000")
        self.assertEqual(cfg.model_endpoint, "http://192.168.1.101:5000")

    def test_model_endpoint_forced_env(self):
        with patch.dict(os.environ, {"MODEL_SERVER_URL": "http://leanlens-model:5000"}):
            cfg = Config(server_url="django")
            self.assertEqual(cfg.model_endpoint, "http://leanlens-model:5000")

    def test_images_dir_from_folder(self):
        cfg = Config(images_root="/var/www/leanlens/images", folder="images/192.168.1.64",
                     camera_ip="192.168.1.64")
        self.assertEqual(cfg.images_dir, "/var/www/leanlens/images/192.168.1.64")

    def test_images_dir_falls_back_to_camera_ip(self):
        cfg = Config(images_root="/var/www/leanlens/images", folder="", camera_ip="10.0.0.5")
        self.assertEqual(cfg.images_dir, "/var/www/leanlens/images/10.0.0.5")


if __name__ == "__main__":
    unittest.main()
