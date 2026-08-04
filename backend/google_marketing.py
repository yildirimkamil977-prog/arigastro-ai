"""Google Ads + Analytics + Search Console integration module."""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric

logger = logging.getLogger("google_marketing")

# Config
GOOGLE_ADS_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "")
GOOGLE_ADS_MCC_ID = os.environ.get("GOOGLE_ADS_MCC_ID", "").replace("-", "")
GOOGLE_ADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GOOGLE_ADS_IMPERSONATED_EMAIL = os.environ.get("GOOGLE_ADS_IMPERSONATED_EMAIL", "")
GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
GSC_SITE_URL = os.environ.get("GSC_SITE_URL", "")
SA_PATH = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "google_service_account.json")

def get_sa_path():
    if os.path.isabs(SA_PATH):
        return SA_PATH
    return os.path.join(os.path.dirname(__file__), SA_PATH)

# ============ GOOGLE ADS ============

def get_ads_client():
    """Get Google Ads API client."""
    from google.ads.googleads.client import GoogleAdsClient
    
    sa_path = get_sa_path()
    config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "json_key_file_path": sa_path,
        "impersonated_email": GOOGLE_ADS_IMPERSONATED_EMAIL,
        "login_customer_id": GOOGLE_ADS_MCC_ID,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)

def fetch_ads_campaigns(date_from: str = None, date_to: str = None) -> list:
    """Fetch campaign performance data from Google Ads."""
    if not GOOGLE_ADS_CUSTOMER_ID or not GOOGLE_ADS_DEVELOPER_TOKEN:
        return []
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    try:
        client = get_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT
                campaign.id, campaign.name, campaign.status,
                campaign.advertising_channel_type,
                campaign_budget.amount_micros,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value,
                metrics.ctr, metrics.average_cpc,
                metrics.cost_per_conversion
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
            AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
        """
        
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        
        campaigns = []
        for row in response:
            campaigns.append({
                "id": str(row.campaign.id),
                "name": row.campaign.name,
                "status": row.campaign.status.name,
                "channel": row.campaign.advertising_channel_type.name,
                "budget": row.campaign_budget.amount_micros / 1_000_000,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": row.metrics.cost_micros / 1_000_000,
                "conversions": round(row.metrics.conversions, 2),
                "conversion_value": round(row.metrics.conversions_value, 2),
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": row.metrics.average_cpc / 1_000_000,
                "cost_per_conversion": row.metrics.cost_per_conversion / 1_000_000 if row.metrics.cost_per_conversion else 0,
                "roas": round(row.metrics.conversions_value / (row.metrics.cost_micros / 1_000_000), 2) if row.metrics.cost_micros > 0 else 0,
            })
        return campaigns
    except Exception as e:
        logger.error(f"Google Ads campaigns error: {e}")
        return [{"error": str(e)}]

def fetch_ads_keywords(date_from: str = None, date_to: str = None, limit: int = 50) -> list:
    """Fetch keyword performance data."""
    if not GOOGLE_ADS_CUSTOMER_ID or not GOOGLE_ADS_DEVELOPER_TOKEN:
        return []
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    try:
        client = get_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                campaign.name,
                ad_group.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value,
                metrics.ctr, metrics.average_cpc
            FROM keyword_view
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
            ORDER BY metrics.cost_micros DESC
            LIMIT {limit}
        """
        
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        
        keywords = []
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000
            keywords.append({
                "keyword": row.ad_group_criterion.keyword.text,
                "match_type": row.ad_group_criterion.keyword.match_type.name,
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": cost,
                "conversions": round(row.metrics.conversions, 2),
                "conversion_value": round(row.metrics.conversions_value, 2),
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": row.metrics.average_cpc / 1_000_000,
                "roas": round(row.metrics.conversions_value / cost, 2) if cost > 0 else 0,
            })
        return keywords
    except Exception as e:
        logger.error(f"Google Ads keywords error: {e}")
        return [{"error": str(e)}]

# ============ GOOGLE ANALYTICS 4 ============

def get_ga4_client():
    """Get GA4 client."""
    sa_path = get_sa_path()
    credentials = service_account.Credentials.from_service_account_file(sa_path, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    return BetaAnalyticsDataClient(credentials=credentials)

def fetch_ga4_overview(date_from: str = None, date_to: str = None) -> dict:
    """Fetch GA4 overview metrics."""
    if not GA4_PROPERTY_ID:
        return {}
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    try:
        client = get_ga4_client()
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
            metrics=[
                Metric(name="sessions"), Metric(name="totalUsers"),
                Metric(name="newUsers"), Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"), Metric(name="screenPageViews"),
                Metric(name="ecommercePurchases"), Metric(name="totalRevenue"),
            ],
        )
        response = client.run_report(request)
        
        if response.rows:
            row = response.rows[0]
            return {
                "sessions": int(row.metric_values[0].value),
                "total_users": int(row.metric_values[1].value),
                "new_users": int(row.metric_values[2].value),
                "bounce_rate": round(float(row.metric_values[3].value) * 100, 1),
                "avg_session_duration": round(float(row.metric_values[4].value), 1),
                "page_views": int(row.metric_values[5].value),
                "purchases": int(row.metric_values[6].value),
                "revenue": round(float(row.metric_values[7].value), 2),
            }
        return {}
    except Exception as e:
        logger.error(f"GA4 overview error: {e}")
        return {"error": str(e)}

def fetch_ga4_traffic_sources(date_from: str = None, date_to: str = None) -> list:
    """Fetch traffic by source/medium."""
    if not GA4_PROPERTY_ID:
        return []
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    try:
        client = get_ga4_client()
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
            dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
            metrics=[
                Metric(name="sessions"), Metric(name="totalUsers"),
                Metric(name="ecommercePurchases"), Metric(name="totalRevenue"),
            ],
            limit=20,
        )
        response = client.run_report(request)
        
        sources = []
        for row in response.rows:
            sources.append({
                "source": row.dimension_values[0].value,
                "medium": row.dimension_values[1].value,
                "sessions": int(row.metric_values[0].value),
                "users": int(row.metric_values[1].value),
                "purchases": int(row.metric_values[2].value),
                "revenue": round(float(row.metric_values[3].value), 2),
            })
        return sorted(sources, key=lambda x: x["sessions"], reverse=True)
    except Exception as e:
        logger.error(f"GA4 traffic sources error: {e}")
        return [{"error": str(e)}]

# ============ GOOGLE SEARCH CONSOLE ============

def fetch_gsc_data(date_from: str = None, date_to: str = None, limit: int = 30) -> list:
    """Fetch Search Console data."""
    if not GSC_SITE_URL:
        return []
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        from googleapiclient.discovery import build
        sa_path = get_sa_path()
        credentials = service_account.Credentials.from_service_account_file(sa_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        service = build("searchconsole", "v1", credentials=credentials)
        
        request = {
            "startDate": date_from,
            "endDate": date_to,
            "dimensions": ["query"],
            "rowLimit": limit,
            "dataState": "final",
        }
        response = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=request).execute()
        
        rows = []
        for row in response.get("rows", []):
            rows.append({
                "query": row["keys"][0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            })
        return rows
    except Exception as e:
        logger.error(f"GSC data error: {e}")
        return [{"error": str(e)}]

# ============ COMBINED DATA ============

def fetch_all_marketing_data(date_from: str = None, date_to: str = None) -> dict:
    """Fetch all marketing data from all sources."""
    return {
        "ads_campaigns": fetch_ads_campaigns(date_from, date_to),
        "ads_keywords": fetch_ads_keywords(date_from, date_to),
        "ga4_overview": fetch_ga4_overview(date_from, date_to),
        "ga4_traffic": fetch_ga4_traffic_sources(date_from, date_to),
        "gsc_queries": fetch_gsc_data(date_from, date_to),
        "date_range": {"from": date_from, "to": date_to},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
