"""
Taxonomy + labeling-tooling tests (ML Training Master Plan Section 2.1/2.2).

Agreement scoring is tested with small, clearly-synthetic label dicts --
that's testing the code's arithmetic, not claiming a real inter-labeler
agreement result (which requires actual humans reading actual resumes).
"""
import json

import pytest

from ml.taxonomy import CATEGORIES, OTHER_GENERAL, validate_category
from ml.labeling import build_labeling_worksheet, compute_agreement, _load_labels


class TestTaxonomy:
    def test_every_category_has_a_nonempty_rule(self):
        from ml.taxonomy import CATEGORY_RULES
        for name in CATEGORIES:
            assert CATEGORY_RULES[name].strip(), f"{name} has no rule"

    def test_other_general_is_in_the_taxonomy(self):
        assert OTHER_GENERAL in CATEGORIES

    def test_validate_category_accepts_known_category(self):
        validate_category("Java Developer")  # must not raise

    def test_validate_category_rejects_unknown_category(self):
        with pytest.raises(ValueError, match="not in the fixed taxonomy"):
            validate_category("Data Scientist")


class TestLabelingWorksheet:
    def test_worksheet_reads_body_text_not_filename(self, tmp_path):
        """Regression guard for the exact mistake Section 2.2 calls out --
        the worksheet must be built from parsed body text, never the raw
        filename string, even though the dataset's own filenames often
        happen to hint at a category."""
        from tests.conftest import DATASET_DIR

        out_path = tmp_path / "worksheet.json"
        n = build_labeling_worksheet(out_path, resume_dir=DATASET_DIR, preview_chars=200)
        if n == 0:
            pytest.skip("Dataset not found -- run from repo checkout with dataset present.")

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["entries"], "worksheet has no entries"
        first = next(iter(data["entries"].values()))
        assert first["category"] is None
        assert isinstance(first["body_text_preview"], str) and len(first["body_text_preview"]) > 0
        # the preview must be real parsed text, not just the filename echoed back
        some_filename = next(iter(data["entries"].keys()))
        assert data["entries"][some_filename]["body_text_preview"] != some_filename


class TestAgreement:
    def _write(self, tmp_path, name, entries):
        path = tmp_path / name
        path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
        return path

    def test_perfect_agreement(self, tmp_path):
        entries = {
            "a.docx": {"category": "Business Analyst"},
            "b.docx": {"category": "Java Developer"},
            "c.docx": {"category": "Project Manager"},
        }
        path_a = self._write(tmp_path, "a.json", entries)
        path_b = self._write(tmp_path, "b.json", entries)

        result = compute_agreement(path_a, path_b)
        assert result["percent_agreement"] == 1.0
        assert result["cohen_kappa"] == 1.0
        assert result["disagreements"] == []

    def test_partial_agreement_reports_disagreements(self, tmp_path):
        path_a = self._write(tmp_path, "a.json", {
            "a.docx": {"category": "Business Analyst"},
            "b.docx": {"category": "Java Developer"},
        })
        path_b = self._write(tmp_path, "b.json", {
            "a.docx": {"category": "Business Systems Analyst"},  # disagreement
            "b.docx": {"category": "Java Developer"},
        })

        result = compute_agreement(path_a, path_b)
        assert result["n_compared"] == 2
        assert result["percent_agreement"] == 0.5
        assert len(result["disagreements"]) == 1
        assert result["disagreements"][0]["filename"] == "a.docx"

    def test_only_compares_overlapping_filenames(self, tmp_path):
        path_a = self._write(tmp_path, "a.json", {"a.docx": {"category": "Business Analyst"}})
        path_b = self._write(tmp_path, "b.json", {
            "a.docx": {"category": "Business Analyst"},
            "z.docx": {"category": "Project Manager"},  # only labeled by b
        })
        result = compute_agreement(path_a, path_b)
        assert result["n_compared"] == 1

    def test_raises_on_no_overlap(self, tmp_path):
        path_a = self._write(tmp_path, "a.json", {"a.docx": {"category": "Business Analyst"}})
        path_b = self._write(tmp_path, "b.json", {"b.docx": {"category": "Java Developer"}})
        with pytest.raises(ValueError, match="No overlapping"):
            compute_agreement(path_a, path_b)

    def test_flat_shape_also_accepted(self, tmp_path):
        """compute_agreement should accept either the full worksheet shape
        ({"entries": {...}}) or a flat {filename: category} dict, since a
        team member might reasonably hand-edit a simplified file."""
        path = tmp_path / "flat.json"
        path.write_text(json.dumps({"a.docx": "Java Developer"}), encoding="utf-8")
        labels = _load_labels(path)
        assert labels == {"a.docx": "Java Developer"}
