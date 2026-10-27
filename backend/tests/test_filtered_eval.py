from eval.retrieval_eval import evaluate


def test_filtered_evaluation_measures_actual_returned_sources(collection):
    contracts = {"a": "Deposit is ten.", "b": "Deposit is ninety."}
    questions = [
        {"id": "a1", "contract": "a", "lang": "en", "question": "deposit?", "answer": [contracts["a"]], "spans": [(0, len(contracts["a"]))]},
        {"id": "b1", "contract": "b", "lang": "en", "question": "deposit?", "answer": [contracts["b"]], "spans": [(0, len(contracts["b"]))]},
    ]
    # The collection's test embedding avoids model downloads and gives every chunk equal similarity.
    embedding = collection._embedding_function
    filtered = evaluate(contracts, questions, embedding, 50, 5, 3, filtered=True)
    unfiltered = evaluate(contracts, questions, embedding, 50, 5, 3, shared=True)
    assert filtered["foreign_share"] == 0
    assert filtered["hit"][3] == 1
    assert filtered["retrieval_path"] == "production store_chunks/search_chunks"
    assert unfiltered["foreign_share"] == 0.5
