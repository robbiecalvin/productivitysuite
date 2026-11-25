import unittest
from suite.contracts import build_contract

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.spec = {"name": "Synthetic task manager", "acceptance_criteria": ["Persist tasks"]}
        self.contract = build_contract(self.spec)

    def test_preserves_requirements(self):
        self.assertEqual(self.contract["project_name"], self.spec["name"])
        self.assertEqual(self.contract["acceptance_criteria"], self.spec["acceptance_criteria"])

    def test_route_contract(self):
        routes = {(r["method"], r["path"]): r["status"] for r in self.contract["routes"]}
        self.assertEqual(routes[("POST", "/api/tasks")], 201)
        self.assertEqual(routes[("DELETE", "/api/tasks/<int:task_id>")], 204)
        self.assertEqual(len(routes), 5)

    def test_repeatable_contract(self):
        self.assertEqual(self.contract, build_contract(self.spec))

    def test_missing_requirements_rejected(self):
        with self.assertRaises(KeyError):
            build_contract({"name": "Incomplete"})
