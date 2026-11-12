"""Kurulan paketin keşif ve lisans bilgilerini koruyan kontroller."""

from importlib.metadata import metadata


def test_package_author():
    assert metadata("turkiye-deprem-verisi")["Author"] == "Ayberk Korkmaz"


def test_package_keywords():
    keywords = set(metadata("turkiye-deprem-verisi")["Keywords"].split(","))
    assert {"earthquake", "seismology", "strong-motion", "turkey", "dataset", "machine-learning"} <= keywords


def test_package_project_urls():
    urls = dict(value.split(", ", 1) for value in metadata("turkiye-deprem-verisi").get_all("Project-URL"))
    assert urls == {
        "Repository": "https://github.com/Ayberkrk/turkiye-deprem-verisi",
        "Dataset": "https://huggingface.co/datasets/Ayberkkr/turkiye-deprem-verisi",
        "Archive": "https://doi.org/10.5281/zenodo.22754705",
        "Changelog": "https://github.com/Ayberkrk/turkiye-deprem-verisi/blob/main/CHANGELOG.md",
    }


def test_package_code_license():
    info = metadata("turkiye-deprem-verisi")
    assert info["License-Expression"] == "MIT"
    assert set(info.get_all("License-File")) == {"LICENSE", "LICENSE-DATA.md"}
    # Veri lisansları kodun MIT ifadesiyle yeniden lisanslanmamalı.
    assert "LICENSE-DATA.md" in info.get_payload()
