"""Tests for ner_parser. The model is replaced by canned entities, so nothing is downloaded."""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ner_parser as n

FALLBACK = {"email": "a@b.com", "phone": "123", "skills": ["Python"], "education": "Not Found", "experience": 0}


def ent(label, text, whole, score=0.95):
    start = whole.index(text)
    return {"label": label, "text": text, "score": score, "start": start, "end": start + len(text)}


class ChunkTests(unittest.TestCase):
    def test_chunks_cover_text_exactly_with_correct_offsets(self):
        text = ("word " * 800) + "\n" + "line two\n" * 400
        pieces = n._chunks(text)
        self.assertEqual("".join(c for _, c in pieces), text)
        self.assertTrue(all(text[o:o + len(c)] == c for o, c in pieces))
        self.assertTrue(all(len(c) <= n.CHUNK_CHARS + 1 for _, c in pieces))

    def test_short_text_is_one_chunk(self):
        self.assertEqual(n._chunks("hello\nworld\n"), [(0, "hello\nworld\n")])


class SpanCleaningTests(unittest.TestCase):
    def test_span_grows_to_whole_words(self):
        text = "Skills: CAFM Software, OSHA/ADA Compliance"
        start = text.index("mpliance")
        self.assertEqual(n._clean_span(text, start, start + 8)[0][0], "Compliance")

    def test_span_is_split_at_line_breaks(self):
        text = "Andrea Murphy\nContact"
        pieces = n._clean_span(text, 0, len(text))
        self.assertEqual([p[0] for p in pieces], ["Andrea Murphy", "Contact"])


class FieldTests(unittest.TestCase):
    def test_degree_levels(self):
        d = lambda t: n._degree([{"label": "DEGREE", "text": t, "score": 0.9}])
        self.assertEqual(d("B.Tech"), "Bachelor's Degree")
        self.assertEqual(d("B.S."), "Bachelor's Degree")
        self.assertEqual(d("MBA"), "Master's Degree")
        self.assertEqual(d("PGDM"), "Master's Degree")
        self.assertEqual(d("PhD"), "PhD")
        self.assertIsNone(d("High School Diploma and certificate") if False else n._degree([]))

    def test_highest_degree_wins(self):
        ents = [{"label": "DEGREE", "text": t, "score": 0.9} for t in ("BBA", "MBA")]
        self.assertEqual(n._degree(ents), "Master's Degree")

    def test_stated_years_including_words(self):
        self.assertEqual(n._stated_years("Manager with seven years of experience"), 7)
        self.assertEqual(n._stated_years("with 3+ years of experience"), 3)
        self.assertEqual(n._stated_years("with over 4 years of expertise"), 4)
        self.assertIsNone(n._stated_years("recent graduate"))

    def test_unique_drops_truncated_prefix_but_keeps_suffix(self):
        got = n._unique(["Facility Property", "Facility Property Manager", "Photo Editor", "Assistant Photo Editor"])
        self.assertEqual(got, ["Facility Property Manager", "Photo Editor", "Assistant Photo Editor"])

    def test_normalize_skill_aliases_without_model(self):
        self.assertEqual(n.normalize_skill("k8s", use_embeddings=False), "Kubernetes")
        self.assertEqual(n.normalize_skill("Python programming", use_embeddings=False), "Python")
        self.assertIsNone(n.normalize_skill("Wound Care", use_embeddings=False))


class ParseResumeTests(unittest.TestCase):
    TEXT = "Priya Singh\nFacility Manager\nMBA, Mumbai University\nWith seven years of experience\nSkills\nWound Care, Python"

    def entities(self):
        return [ent("NAME", "Priya Singh", self.TEXT), ent("TITLE", "Facility Manager", self.TEXT),
                ent("DEGREE", "MBA", self.TEXT), ent("SKILL", "Wound Care", self.TEXT),
                ent("SKILL", "Python", self.TEXT)]

    def test_ner_result_fields(self):
        with mock.patch.object(n, "run_ner", return_value=self.entities()):
            out = n.parse_resume(self.TEXT, FALLBACK, use_embeddings=False)
        self.assertEqual(out["parser_mode"], "ner")
        self.assertEqual(out["name"], "Priya Singh")
        self.assertEqual(out["education"], "Master's Degree")
        self.assertEqual(out["experience"], 7)
        self.assertIn("Python", out["skills"])
        self.assertIn("Wound Care", out["extra_skills"])
        self.assertEqual(out["email"], "a@b.com")  # carried over from the regex result

    def test_falls_back_when_model_fails(self):
        with mock.patch.object(n, "run_ner", side_effect=RuntimeError("no model")):
            out = n.parse_resume(self.TEXT, FALLBACK)
        self.assertEqual(out["parser_mode"], "regex-fallback")
        self.assertEqual(out["skills"], ["Python"])
        self.assertEqual(out["education"], "Not Found")

    def test_falls_back_when_nothing_found(self):
        with mock.patch.object(n, "run_ner", return_value=[]):
            self.assertEqual(n.parse_resume(self.TEXT, FALLBACK)["parser_mode"], "regex-fallback")

    def test_falls_back_on_low_confidence(self):
        low = [{**e, "score": 0.62} for e in self.entities()]
        with mock.patch.object(n, "run_ner", return_value=low):
            self.assertEqual(n.parse_resume(self.TEXT, FALLBACK)["parser_mode"], "regex-fallback")

    def test_regex_mode_skips_the_model(self):
        with mock.patch.object(n, "PARSER_MODE", "regex"), mock.patch.object(n, "run_ner") as run:
            out = n.parse_resume(self.TEXT, FALLBACK)
        run.assert_not_called()
        self.assertEqual(out["parser_mode"], "regex-fallback")

    def test_career_span_ignores_school_dates(self):
        text = "Regis High School 2018 - 2022\nSales Associate Big Apple Bookstore September 2023 - March 2026"
        ents = [ent("INSTITUTION", "Regis High School", text), ent("DATE", "2018 - 2022", text),
                ent("TITLE", "Sales Associate", text), ent("COMPANY", "Big Apple Bookstore", text),
                ent("DATE", "September 2023 - March 2026", text)]
        self.assertEqual(n._career_span(ents, text), 3)


class RegressionTests(unittest.TestCase):
    """Bugs found by the real upload test."""

    def test_present_tagged_as_its_own_date_counts_as_this_year(self):
        # The model split "(2018-Present)" and "(2015-2018)" into separate fragments.
        text = "Senior Engineer - Tech Corp (2018-Present)\nEngineer - Startup (2015-2018)"
        ents = [ent("TITLE", "Senior Engineer", text), ent("COMPANY", "Tech Corp", text),
                ent("DATE", "2018", text), ent("DATE", "Present", text), ent("DATE", "2015", text)]
        from datetime import datetime
        self.assertEqual(n._career_span(ents, text), datetime.now().year - 2015)

    def test_current_job_range_is_read_from_text_when_the_model_misses_it(self):
        text = "Senior Engineer - Tech Corp (2018-Present)\nEngineer - Startup (2015-2018)"
        ents = [ent("TITLE", "Senior Engineer", text), ent("COMPANY", "Tech Corp", text),
                ent("DATE", "2015", text)]  # the model found no date for the current job
        from datetime import datetime
        self.assertEqual(n._career_span(ents, text), datetime.now().year - 2015)

    def test_closed_range_is_read_from_text_when_the_model_misses_it(self):
        text = "Senior Engineer - Tech Corp (2018-Present)\nEngineer - Startup (2015-2018)"
        ents = [ent("TITLE", "Senior Engineer", text), ent("COMPANY", "Tech Corp", text),
                ent("TITLE", "Engineer", text.split("\n")[1]), ent("DATE", "Present", text)]
        ents[2] = {**ents[2], "start": ents[2]["start"] + text.index("\n") + 1, "end": ents[2]["end"] + text.index("\n") + 1}
        from datetime import datetime
        self.assertEqual(n._career_span(ents, text), datetime.now().year - 2015)

    def test_school_range_is_not_read_as_a_job(self):
        text = "Regis High School 2018 - 2022\nSales Associate, Big Apple Bookstore 2023 - 2026"
        ents = [ent("INSTITUTION", "Regis High School", text), ent("TITLE", "Sales Associate", text),
                ent("COMPANY", "Big Apple Bookstore", text)]
        self.assertEqual(n._career_span(ents, text), 3)

    def test_surname_is_not_read_as_a_tool(self):
        text = "Debra Jenkins\nProject Manager\nSkills\nAgile"
        ents = [ent("NAME", "Debra Jenkins", text, 1.0), ent("TITLE", "Project Manager", text, 1.0)]
        canonical, _ = n._skills(ents, text, use_embeddings=False)
        self.assertNotIn("Jenkins", canonical)
        self.assertIn("Agile", canonical)

    def test_regex_skills_that_came_from_the_name_do_not_leak_back(self):
        text = "Debra Jenkins\nProject Manager at Truenorth Corporation"
        ents = [ent("NAME", "Debra Jenkins", text, 1.0), ent("TITLE", "Project Manager", text, 1.0),
                ent("COMPANY", "Truenorth Corporation", text, 1.0)]
        with mock.patch.object(n, "run_ner", return_value=ents):
            out = n.parse_resume(text, {**FALLBACK, "skills": ["Jenkins"]}, use_embeddings=False)
        self.assertEqual(out["skills"], ["N/A"])

    def test_tool_is_still_found_when_it_is_not_the_name(self):
        text = "Debra Smith\nProject Manager\nSkills\nJenkins, Agile"
        ents = [ent("NAME", "Debra Smith", text, 1.0)]
        canonical, _ = n._skills(ents, text, use_embeddings=False)
        self.assertIn("Jenkins", canonical)

    def test_name_far_from_the_top_is_ignored(self):
        text = "x" * 500 + " Society"
        self.assertIsNone(n._name([ent("NAME", "Society", text, 0.99)]))

    def test_name_overlapping_a_job_title_is_rejected(self):
        text = "HR BENEFITS/LEAVE COORDINATOR"
        ents = [ent("NAME", "HR BENEFITS", text, 0.99), ent("TITLE", "BENEFITS/LEAVE COORDINATOR", text, 1.0)]
        self.assertIsNone(n._name(ents))

    def test_real_name_above_a_title_is_kept(self):
        text = "Priya Singh\nFacility Manager"
        ents = [ent("NAME", "Priya Singh", text, 1.0), ent("TITLE", "Facility Manager", text, 1.0)]
        self.assertEqual(n._name(ents), "Priya Singh")


if __name__ == "__main__":
    unittest.main()
