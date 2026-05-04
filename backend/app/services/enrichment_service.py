"""
Text enrichment using Azure AI Language (Text Analytics).

Called during the indexing pipeline to enrich each chunk with:
  - Key phrases
  - Named entities (people, organizations, locations, dates, etc.)
  - Sentiment (positive / neutral / negative + confidence scores)
"""

import logging
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from app.config import get_settings

logger = logging.getLogger(__name__)


class EnrichmentService:
    def __init__(self):
        settings = get_settings()
        self._client = TextAnalyticsClient(
            endpoint=settings.azure_language_endpoint,
            credential=AzureKeyCredential(settings.azure_language_key),
        )

    def enrich(self, text: str) -> dict:
        """
        Run all enrichments on a single text chunk.

        Returns a dict with:
          - keyphrases: list[str]
          - entities: list[dict] with name, category, subcategory
          - sentiment: str ("positive" | "neutral" | "negative" | "mixed")
          - sentiment_scores: dict with positive, neutral, negative floats
        """
        result = {
            "keyphrases": [],
            "entities": [],
            "sentiment": "neutral",
            "sentiment_scores": {"positive": 0.0, "neutral": 1.0, "negative": 0.0},
        }

        if not text or not text.strip():
            return result

        # Truncate to 5120 chars (Text Analytics limit per document)
        truncated = text[:5120]

        try:
            result["keyphrases"] = self._extract_key_phrases(truncated)
        except Exception as e:
            logger.warning(f"Key phrase extraction failed: {e}")

        try:
            result["entities"] = self._recognize_entities(truncated)
        except Exception as e:
            logger.warning(f"Entity recognition failed: {e}")

        try:
            sentiment_data = self._analyze_sentiment(truncated)
            result["sentiment"] = sentiment_data["sentiment"]
            result["sentiment_scores"] = sentiment_data["scores"]
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")

        return result

    def enrich_batch(self, texts: list[str]) -> list[dict]:
        """Enrich multiple texts. Returns a list of enrichment dicts in the same order."""
        if not texts:
            return []

        truncated = [t[:5120] for t in texts]
        results = [
            {
                "keyphrases": [],
                "entities": [],
                "sentiment": "neutral",
                "sentiment_scores": {"positive": 0.0, "neutral": 1.0, "negative": 0.0},
            }
            for _ in texts
        ]

        # Batch key phrases
        try:
            kp_response = self._client.extract_key_phrases(truncated)
            for i, doc in enumerate(kp_response):
                if not doc.is_error:
                    results[i]["keyphrases"] = list(doc.key_phrases)
        except Exception as e:
            logger.warning(f"Batch key phrase extraction failed: {e}")

        # Batch entities
        try:
            ent_response = self._client.recognize_entities(truncated)
            for i, doc in enumerate(ent_response):
                if not doc.is_error:
                    results[i]["entities"] = [
                        {
                            "name": ent.text,
                            "category": ent.category,
                            "subcategory": ent.subcategory or "",
                            "confidence": round(ent.confidence_score, 2),
                        }
                        for ent in doc.entities
                    ]
        except Exception as e:
            logger.warning(f"Batch entity recognition failed: {e}")

        # Batch sentiment
        try:
            sent_response = self._client.analyze_sentiment(truncated)
            for i, doc in enumerate(sent_response):
                if not doc.is_error:
                    results[i]["sentiment"] = doc.sentiment
                    results[i]["sentiment_scores"] = {
                        "positive": round(doc.confidence_scores.positive, 3),
                        "neutral": round(doc.confidence_scores.neutral, 3),
                        "negative": round(doc.confidence_scores.negative, 3),
                    }
        except Exception as e:
            logger.warning(f"Batch sentiment analysis failed: {e}")

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_key_phrases(self, text: str) -> list[str]:
        response = self._client.extract_key_phrases([text])
        doc = response[0]
        if doc.is_error:
            logger.warning(f"Key phrase error: {doc.error}")
            return []
        return list(doc.key_phrases)

    def _recognize_entities(self, text: str) -> list[dict]:
        response = self._client.recognize_entities([text])
        doc = response[0]
        if doc.is_error:
            logger.warning(f"Entity error: {doc.error}")
            return []
        return [
            {
                "name": ent.text,
                "category": ent.category,
                "subcategory": ent.subcategory or "",
                "confidence": round(ent.confidence_score, 2),
            }
            for ent in doc.entities
        ]

    def _analyze_sentiment(self, text: str) -> dict:
        response = self._client.analyze_sentiment([text])
        doc = response[0]
        if doc.is_error:
            logger.warning(f"Sentiment error: {doc.error}")
            return {"sentiment": "neutral", "scores": {"positive": 0, "neutral": 1, "negative": 0}}
        return {
            "sentiment": doc.sentiment,
            "scores": {
                "positive": round(doc.confidence_scores.positive, 3),
                "neutral": round(doc.confidence_scores.neutral, 3),
                "negative": round(doc.confidence_scores.negative, 3),
            },
        }
