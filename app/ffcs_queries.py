CAMPAIGN_SOURCE_COLLECTION = "Plates"


def campaign_discovery_pipeline(user_account: str):
    """Build the FFCS campaign-discovery query for a user account."""
    return [
        {
            "$match": {
                "userAccount": user_account,
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
