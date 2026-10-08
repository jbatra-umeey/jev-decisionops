import unittest
import app
class PolicyTests(unittest.TestCase):
    def test_hard_deny_overrides_model_allow(self):
        result=app.enforce_policy('tools','github.delete_repository',{'permission':{'choice':'allow','confidence':1}})
        self.assertEqual(result['action'],'BLOCK')
    def test_unknown_guardrail_fails_closed(self):
        self.assertEqual(app.enforce_policy('guardrails','hello',{'risk':{'choice':'unknown'}})['action'],'REVIEW')
    def test_confidence_requires_threshold(self):
        self.assertEqual(app.enforce_policy('confidence','x',{'action':{'choice':'proceed','confidence':.70}})['action'],'CONFIRM')
    def test_scenario_coverage(self):
        self.assertEqual(len(app.SCENARIOS),6)
        self.assertEqual({q['type'] for x in app.SCENARIOS.values() for q in x['questions'].values()},{'choice','score','noul'})
if __name__=='__main__':unittest.main()
