# tests package — ajoute src/ au path pour importer config/logic/reporter/gdpr
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
