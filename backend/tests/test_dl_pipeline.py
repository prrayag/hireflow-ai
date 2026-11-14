import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dl_pipeline import experience_match, extract_skills, process_resume_record, sentence_chunks, skill_gap


class DLPipelineTests(unittest.TestCase):
    def test_skill_aliases_are_canonicalized(self):
        skills = extract_skills("Built APIs with nodejs, k8s, sklearn and AWS.")
        self.assertIn("Node.js", skills)
        self.assertIn("Kubernetes", skills)
        self.assertIn("scikit-learn", skills)
        self.assertIn("AWS", skills)

    def test_section_aware_chunks(self):
        chunks = sentence_chunks("SUMMARY\nPython engineer.\nSKILLS\nPython, Docker, AWS.")
        self.assertEqual([chunk["section"] for chunk in chunks], ["summary", "skills"])

    def test_skill_gap(self):
        gap = skill_gap(["Python", "AWS"], "Need Python, AWS and Kubernetes")
        self.assertEqual(gap["matched_skills"], ["Python", "AWS"])
        self.assertEqual(gap["missing_skills"], ["Kubernetes"])
        self.assertAlmostEqual(gap["skill_coverage"], 66.67, places=2)

    def test_experience_is_relative_to_jd(self):
        self.assertEqual(experience_match(3, "Requires 5+ years experience"), 60.0)
        self.assertEqual(experience_match(8, "Requires 5 years experience"), 100.0)

    def test_spark_safe_resume_record(self):
        records = process_resume_record({
            "resume_id": "r-1", "name": "Test Candidate",
            "text": "SUMMARY\nPython engineer.\nSKILLS\nPython and AWS.",
            "skills": ["Python", "AWS"], "experience": 3,
        })
        self.assertEqual(records[0]["resume_id"], "r-1")
        self.assertEqual(records[0]["metadata"]["name"], "Test Candidate")
        self.assertNotIn("embedding", records[0])


if __name__ == "__main__":
    unittest.main()
