import itertools
import sys
import unittest
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

import ner_parser
from dl_pipeline import experience_from_date_ranges, skill_gap
from human_benchmark import quadratic_weighted_kappa
from ner_data import entity_scores
from ner_models import (CRF, LABELS, BiLSTMCRF, bio_spans, encode_bilstm_batch,
                        merge_skillspan_tags, repair_bio, tokenize)
from resume_parser import extract_experience_years, extract_metadata


class CRFTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(0)
        self.crf = CRF(3)
        self.emissions = torch.randn(1, 4, 3)
        self.mask = torch.ones(1, 4, dtype=torch.bool)

    def _path_score(self, path):
        return float(self.crf._path_score(self.emissions, torch.tensor([path]), self.mask)[0])

    def test_viterbi_matches_brute_force(self):
        paths = list(itertools.product(range(3), repeat=4))
        best = max(paths, key=self._path_score)
        self.assertEqual(self.crf.decode(self.emissions, self.mask)[0], list(best))

    def test_partition_function_normalises_all_paths(self):
        paths = itertools.product(range(3), repeat=4)
        total = torch.logsumexp(torch.tensor([self._path_score(p) for p in paths]), dim=0)
        self.assertAlmostEqual(float(self.crf._log_partition(self.emissions, self.mask)[0]),
                               float(total), places=4)

    def test_masked_positions_are_ignored(self):
        emissions = torch.randn(2, 5, 3)
        mask = torch.tensor([[1, 1, 1, 0, 0], [1, 1, 1, 1, 1]], dtype=torch.bool)
        short = self.crf.decode(emissions[:1, :3], mask[:1, :3])[0]
        self.assertEqual(self.crf.decode(emissions, mask)[0], short)
        self.assertEqual(len(self.crf.decode(emissions, mask)[1]), 5)


class BiLSTMCRFTests(unittest.TestCase):
    def test_loss_and_prediction_shapes(self):
        words = {"<pad>": 0, "<unk>": 1, "python": 2, "and": 3}
        chars = {"<pad>": 0, "<unk>": 1, **{c: i + 2 for i, c in enumerate("Pythonad")}}
        model = BiLSTMCRF(len(words), len(chars), len(LABELS), hidden_dim=8, word_dim=8,
                          char_dim=4, char_filters=4)
        w, c, mask = encode_bilstm_batch([["Python", "and", "Go"], ["Python"]], words, chars)
        tags = torch.zeros_like(w)
        loss = model.loss(w, c, tags, mask)
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        paths, confidences = model.predict(w, c, mask)
        self.assertEqual([len(p) for p in paths], [3, 1])
        self.assertTrue(all(0.0 <= x <= 1.0 for row in confidences for x in row))


class BioHelperTests(unittest.TestCase):
    def test_tokenize_keeps_skill_punctuation(self):
        tokens = [t for t, _, _ in tokenize("Used Node.js, C++ and C# (on AWS).")]
        self.assertEqual(tokens, ["Used", "Node.js", ",", "C++", "and", "C#", "(", "on", "AWS", ")."])

    def test_tokenize_offsets_point_back_to_text(self):
        text = "• Python, CI/CD"
        self.assertEqual([text[s:e] for _, s, e in tokenize(text)], ["•", "Python", ",", "CI/CD"])

    def test_merge_prefers_knowledge_and_repairs_bio(self):
        merged = merge_skillspan_tags(["B", "I", "O", "O"], ["O", "B", "I", "O"])
        self.assertEqual(merged, ["B-SOFT", "B-TECH", "I-TECH", "O"])

    def test_repair_and_spans(self):
        labels = repair_bio(["I-TECH", "I-TECH", "O", "B-SOFT", "I-TECH"])
        self.assertEqual(labels, ["B-TECH", "I-TECH", "O", "B-SOFT", "B-TECH"])
        self.assertEqual(bio_spans(labels), [("TECH", 0, 2), ("SOFT", 3, 4), ("TECH", 4, 5)])

    def test_entity_scores_require_exact_spans(self):
        gold = [["B-TECH", "I-TECH", "O", "B-SOFT"]]
        predicted = [["B-TECH", "O", "O", "B-SOFT"]]
        scores = entity_scores(gold, predicted)
        self.assertEqual(scores["TECH"]["f1"], 0.0)
        self.assertEqual(scores["SOFT"]["f1"], 1.0)
        self.assertEqual(scores["micro"]["precision"], 0.5)


class ExperienceTests(unittest.TestCase):
    TODAY = (2026, 11)

    def test_month_year_ranges(self):
        self.assertEqual(experience_from_date_ranges("Engineer Jan 2019 - Mar 2022", self.TODAY), 3.2)
        self.assertEqual(experience_from_date_ranges("Analyst 06/2019 – Present", self.TODAY), 7.5)

    def test_overlaps_merged_and_education_ignored(self):
        text = ("EXPERIENCE\nDeveloper Jun 2019 - Aug 2021\nLead Jan 2021 - Dec 2022\n"
                "EDUCATION\nB.Tech 2014 - 2018")
        self.assertEqual(experience_from_date_ranges(text, self.TODAY), 3.6)

    def test_no_dates(self):
        self.assertEqual(experience_from_date_ranges("Python developer", self.TODAY), 0.0)

    def test_explicit_statement_still_wins(self):
        self.assertEqual(extract_experience_years("I have 4 years of experience. Jan 2010 - Present"), 4)

    def test_month_before_end_year_no_longer_gives_zero(self):
        self.assertGreater(extract_experience_years("Backend Engineer, Acme, Mar 2019 – Feb 2022"), 2.5)


class HybridSkillTests(unittest.TestCase):
    class FakeTagger:
        name = "fake-ner"

        def predict(self, token_lists):
            labels, confidences = [], []
            for tokens in token_lists:
                row = ["B-TECH" if t in {"Snowflake", "k8s", "B.Tech"} else
                       "B-SOFT" if t == "team" else "I-SOFT" if t == "player" else
                       "B-SOFT" if t == "Wrote" else "O" for t in tokens]
                labels.append(row)
                confidences.append([0.9] * len(tokens))
            return labels, confidences

    def setUp(self):
        self._saved = (ner_parser._tagger, ner_parser._tagger_loaded)

    def tearDown(self):
        ner_parser._tagger, ner_parser._tagger_loaded = self._saved

    def test_dictionary_fallback_without_model(self):
        ner_parser._tagger, ner_parser._tagger_loaded = None, True
        parsed = ner_parser.parse_skills("Python and Snowflake")
        self.assertEqual(parsed["skills"], ["Python"])
        self.assertEqual(parsed["skill_parser"], "dictionary")

    def test_ner_adds_new_skills_and_canonicalises_aliases(self):
        ner_parser._tagger, ner_parser._tagger_loaded = self.FakeTagger(), True
        parsed = ner_parser.parse_skills("Python, k8s and Snowflake\nB.Tech\nWrote code as a team player")
        self.assertEqual(parsed["skills"], ["Python", "Kubernetes", "Snowflake"])
        self.assertEqual(parsed["ner_only_skills"], ["Snowflake"])
        self.assertEqual(parsed["soft_skills"], ["team player"])  # one-word spans are dropped
        self.assertEqual(parsed["skill_parser"], "fake-ner+dictionary")

    def test_education_section_and_leading_dot(self):
        class Tagger:
            name = "fake"

            def predict(self, token_lists):
                tech = {".NET", "Computer"}
                return ([["B-TECH" if t in tech else "I-TECH" if t == "Science" else "O"
                          for t in tokens] for tokens in token_lists],
                        [[0.9] * len(tokens) for tokens in token_lists])

        ner_parser._tagger, ner_parser._tagger_loaded = Tagger(), True
        parsed = ner_parser.parse_skills("EXPERIENCE\nBuilt services in .NET.\nEDUCATION\nB.S. Computer Science")
        self.assertEqual(parsed["ner_only_skills"], [".NET"])

    def test_inference_error_falls_back(self):
        class Broken:
            name = "broken"

            def predict(self, token_lists):
                raise RuntimeError("boom")

        ner_parser._tagger, ner_parser._tagger_loaded = Broken(), True
        self.assertEqual(ner_parser.parse_skills("Python")["skill_parser"], "dictionary")

    def test_metadata_phone_ignores_year_ranges(self):
        ner_parser._tagger, ner_parser._tagger_loaded = None, True
        meta = extract_metadata("Asha\nB.Tech 2014 - 2018\nPhone: +91 98765 43210")
        self.assertEqual(meta["phone"], "+91 98765 43210")


class SkillGapAndBenchmarkTests(unittest.TestCase):
    def test_skill_gap_with_ner_jd_skills_is_case_insensitive(self):
        gap = skill_gap(["python", "Snowflake"], "ignored", jd_skills=["Python", "snowflake", "dbt"])
        self.assertEqual(gap["matched_skills"], ["Python", "snowflake"])
        self.assertEqual(gap["missing_skills"], ["dbt"])

    def test_weighted_kappa(self):
        self.assertAlmostEqual(quadratic_weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]), 1.0)
        self.assertLess(quadratic_weighted_kappa([0, 0, 3, 3], [3, 3, 0, 0]), 0.0)


if __name__ == "__main__":
    unittest.main()
