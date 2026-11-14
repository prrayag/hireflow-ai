import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import skill_matcher
from dl_pipeline import extract_jd_phrases, skill_gap


class PhraseExtractionTests(unittest.TestCase):
    def test_reads_required_list(self):
        jd = "Photo Editor wanted. Required: Adobe Photoshop, Lightroom, colour grading, image management."
        self.assertEqual(extract_jd_phrases(jd), ["Adobe Photoshop", "Lightroom", "colour grading", "image management"])

    def test_reads_responsibilities_and_splits_on_and(self):
        jd = "Responsibilities include patient care, wound care, case management and surgical support."
        self.assertEqual(extract_jd_phrases(jd), ["patient care", "wound care", "case management", "surgical support"])

    def test_drops_numbers_filler_and_dictionary_skills(self):
        jd = "Requires strong communication, 5 years of experience, Python and Docker."
        self.assertEqual(extract_jd_phrases(jd), ["communication"])  # Python/Docker are dictionary skills

    def test_no_cue_means_no_phrases(self):
        self.assertEqual(extract_jd_phrases("We are a friendly team in a great office."), [])


class SkillGapTests(unittest.TestCase):
    JD = "Required: wound care, case management. Python is a plus."

    def test_default_behaviour_is_unchanged(self):
        gap = skill_gap(["Python"], self.JD)
        self.assertEqual(gap["jd_skills"], ["Python"])
        self.assertEqual(gap["skill_coverage"], 100.0)

    def test_free_text_phrases_ignored_without_match_fn(self):
        gap = skill_gap(["N/A"], self.JD, jd_phrases=["wound care"], candidate_extra=["Wound Care"])
        self.assertEqual(gap["skill_coverage"], 0.0)

    def test_phrases_count_when_matched(self):
        fake = lambda phrases, pool: {p for p in phrases if p == "wound care"}
        gap = skill_gap(["N/A"], self.JD, jd_phrases=["wound care", "case management"],
                        candidate_extra=["Wound Care"], match_fn=fake)
        self.assertEqual(gap["matched_skills"], ["wound care"])
        self.assertEqual(gap["missing_skills"], ["Python", "case management"])
        self.assertAlmostEqual(gap["skill_coverage"], 100 / 3, places=1)

    def test_phrase_only_jd_gets_a_real_coverage(self):
        jd = "Required: wound care, surgical care."
        fake = lambda phrases, pool: set(phrases[:1])
        gap = skill_gap(["N/A"], jd, jd_phrases=["wound care", "surgical care"], candidate_extra=["x"], match_fn=fake)
        self.assertEqual(gap["skill_coverage"], 50.0)

    def test_empty_candidate_pool_matches_nothing(self):
        fake = mock.Mock(return_value={"wound care"})
        gap = skill_gap(["N/A"], self.JD, jd_phrases=["wound care"], candidate_extra=[], match_fn=fake)
        fake.assert_not_called()
        self.assertEqual(gap["matched_skills"], [])


class LexicalMatchTests(unittest.TestCase):
    def test_lexical_rules(self):
        self.assertTrue(skill_matcher._lexical("Wound Care", ["wound care"]))
        self.assertTrue(skill_matcher._lexical("colour grading", ["Color grading"]))  # spelling variant
        self.assertTrue(skill_matcher._lexical("wound care", ["Advanced wound care"]))
        self.assertFalse(skill_matcher._lexical("wound care", ["Surgical Care"]))

    def test_encoder_failure_falls_back_to_lexical_only(self):
        with mock.patch.dict(sys.modules, {"processor": None}):  # makes `from processor import ...` fail
            hits = skill_matcher.match_skills(["wound care", "tax accounting"], ["Wound Care"])
        self.assertEqual(hits, {"wound care"})


if __name__ == "__main__":
    unittest.main()
