import sys
from pathlib import Path


APP_DIRECTORY = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIRECTORY))

from ffcs_queries import CAMPAIGN_SOURCE_COLLECTION, campaign_discovery_pipeline


def test_campaign_discovery_uses_the_ffcs_plates_collection():
    assert CAMPAIGN_SOURCE_COLLECTION == "Plates"


def test_campaign_discovery_matches_user_and_groups_campaign_ids():
    assert campaign_discovery_pipeline("e12345") == [
        {
            "$match": {
                "userAccount": "e12345",
            }
        },
        {
            "$group": {
                "_id": {
                    "campaignId": "$campaignId",
                }
            }
        },
    ]
