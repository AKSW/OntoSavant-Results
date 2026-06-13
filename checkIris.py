# /// script
# dependencies = [
#     "requests"
# ]
# ///
import json
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse

import requests

IRI_RE = re.compile(r'https?://[^\s<>"\')\]]+')


def extract_iris(text):
    for match in IRI_RE.finditer(text):
        iri = match.group(0)
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        context = text[start:end]
        if "prefix" not in context.lower() and "namespace" not in context.lower():
            yield iri, context


def check_title(text, title) -> bool | None:
    """check if the title is present in the text."""
    if not title or not title.strip():
        print("Title is empty, skipping title check.")
        return None
    if not text or not text.strip():
        print("Text is empty!")
        return False
    return title in text

def get_title_from_url(url):
    title = urlparse(url).fragment or urlparse(url).path.split("/")[-1]
    return title


def check_iri(iri, timeout=10):
    title = get_title_from_url(iri)
    try:
        response = requests.get(
            iri,
            allow_redirects=True,
            timeout=timeout,
            # try to get rdf turtle format
            headers={"Accept": "text/turtle"},
        )
        reachable = (response.status_code == 200) or response.status_code
        final_url = response.url
        status = response.status_code
        title_in_result = check_title(response.text, title)

        return {
            "reachable": reachable,
            "final_url": final_url,
            "title": title,
            "title in result": title_in_result,
        }
    except requests.RequestException as exc:
        return {
            "reachable": False,
            "final_url": None,
            "title": "",
            "title in result": "",
            "error": str(exc),
        }


def main(json_file):
    data = json.loads(Path(json_file).read_text(encoding="utf-8"))
    assert isinstance(data, list), "Expected the JSON file to contain an array of objects."
    
    summary = {}

    for index, item in enumerate(data):
        assert isinstance(item, dict), f"Expected each item in the array to be an object, but got {type(item)} at index {index}."
        id = item.get("id", f"index_{index}")
        text = item.get("model_answer", None)
        iris = list(extract_iris(text)) if text else []

        response_ok = 0
        titles_in_result = 0
        print(f"Processing item with id: {id} (index: {index}), found {len(iris)} IRIs:")
        for iri, context in extract_iris(text):
            result = check_iri(iri)
            if True == result.get("reachable"):
                response_ok += 1
            if result.get("title in result"):
                titles_in_result += 1

            print("  IRI:", iri)
            print(
                "  Check:",
                "    reachable=" + str(result.get("reachable")),
                "    title in result=" + repr(result.get("title in result")),
                "    title=" + repr(result.get("title")),
                "    final_url=" + str(result.get("final_url")),
            )
            if "error" in result:
                print("  Error:", result["error"])
            print("  " + ("-" * 20))
            print("  Context:", context)
        summary[index] = {
            "id": id,
            "total_iris": len(iris),
            "reachable_iris": response_ok,
            "titles_in_result": titles_in_result,
        }
        print(f"  Summary: {response_ok}/{len(iris)} IRIs are reachable, {titles_in_result}/{len(iris)} responses contain the title.")
        print("  " + ("=" * 20))
    print("Overall Summary:")
    print("Index | ID | Total IRIs | Reachable IRIs | Titles in Result")
    for index, item in summary.items():
        print(f"{index} | {item['id']} | {item['total_iris']} | {item['reachable_iris']} | {item['titles_in_result']}")
    print(f"total | | {sum(item['total_iris'] for item in summary.values())} | {sum(item['reachable_iris'] for item in summary.values())} | {sum(item['titles_in_result'] for item in summary.values())}")
    count_with_at_least_one_good_iri = sum(1 for item in summary.values() if item['reachable_iris'] > 0 and item['titles_in_result'] > 0)
    count_with_all_iris_reachable = sum(1 for item in summary.values() if item['total_iris'] > 0 and item['reachable_iris'] == item['total_iris'])
    count_with_all_iris_good = sum(1 for item in summary.values() if item['total_iris'] > 0 and item['reachable_iris'] == item['total_iris'] and item['titles_in_result'] == item['total_iris'])
    print(f"Answers with at least one reachable IRI with title in result: {count_with_at_least_one_good_iri} ({count_with_at_least_one_good_iri / len(summary) * 100:.2f}%)")
    print(f"Answers with all IRIs reachable: {count_with_all_iris_reachable} ({count_with_all_iris_reachable / len(summary) * 100:.2f}%)")
    print(f"Answers with all IRIs good: {count_with_all_iris_good} ({count_with_all_iris_good / len(summary) * 100:.2f}%)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check IRIs in a JSON file.")
    parser.add_argument("json_file", nargs="?", default="qa.json", help="Path to the input JSON file.")
    args = parser.parse_args()
    main(args.json_file)