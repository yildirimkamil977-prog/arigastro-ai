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
GOOGLE_ADS_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_ADS_OAUTH_CLIENT_ID", "")
GOOGLE_ADS_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_ADS_OAUTH_CLIENT_SECRET", "")
GOOGLE_ADS_REFRESH_TOKEN = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", "")
GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
GSC_SITE_URL = os.environ.get("GSC_SITE_URL", "")
SA_PATH = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "google_service_account.json")

def get_sa_path():
    if os.path.isabs(SA_PATH):
        return SA_PATH
    return os.path.join(os.path.dirname(__file__), SA_PATH)

# ============ GOOGLE ADS ============

def get_ads_client():
    """Get Google Ads API client using OAuth2 refresh token."""
    from google.ads.googleads.client import GoogleAdsClient
    
    config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": GOOGLE_ADS_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_ADS_OAUTH_CLIENT_SECRET,
        "refresh_token": GOOGLE_ADS_REFRESH_TOKEN,
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

# ============ SEARCH TERMS REPORT ============

def fetch_search_terms(date_from: str = None, date_to: str = None, limit: int = 200) -> list:
    """Fetch actual search terms that triggered ads."""
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
                search_term_view.search_term,
                search_term_view.status,
                campaign.name,
                ad_group.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value,
                metrics.ctr, metrics.average_cpc
            FROM search_term_view
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
                AND metrics.impressions > 0
            ORDER BY metrics.cost_micros DESC
            LIMIT {limit}
        """
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        terms = []
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000
            conv_value = round(row.metrics.conversions_value, 2)
            terms.append({
                "term": row.search_term_view.search_term,
                "status": row.search_term_view.status.name,
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(cost, 2),
                "conversions": round(row.metrics.conversions, 2),
                "conversion_value": conv_value,
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2),
                "roas": round(conv_value / cost, 2) if cost > 0 else 0,
            })
        return terms
    except Exception as e:
        logger.error(f"Search terms error: {e}")
        return [{"error": str(e)}]

# ============ QUALITY SCORE ============

def fetch_keyword_quality_scores(limit: int = 100) -> list:
    """Fetch keyword quality scores with components."""
    if not GOOGLE_ADS_CUSTOMER_ID or not GOOGLE_ADS_DEVELOPER_TOKEN:
        return []
    try:
        client = get_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        query = f"""
            SELECT
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.quality_info.quality_score,
                ad_group_criterion.quality_info.creative_quality_score,
                ad_group_criterion.quality_info.post_click_quality_score,
                ad_group_criterion.quality_info.search_predicted_ctr,
                campaign.name,
                ad_group.name,
                ad_group_criterion.status,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value
            FROM keyword_view
            WHERE ad_group_criterion.status != 'REMOVED'
                AND segments.date DURING LAST_30_DAYS
            ORDER BY metrics.cost_micros DESC
            LIMIT {limit}
        """
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        keywords = []
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000
            qs = row.ad_group_criterion.quality_info
            keywords.append({
                "keyword": row.ad_group_criterion.keyword.text,
                "match_type": row.ad_group_criterion.keyword.match_type.name,
                "status": row.ad_group_criterion.status.name,
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "quality_score": qs.quality_score if qs.quality_score else None,
                "creative_quality": qs.creative_quality_score.name if qs.creative_quality_score else None,
                "landing_page_quality": qs.post_click_quality_score.name if qs.post_click_quality_score else None,
                "expected_ctr": qs.search_predicted_ctr.name if qs.search_predicted_ctr else None,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(cost, 2),
                "conversions": round(row.metrics.conversions, 2),
                "conversion_value": round(row.metrics.conversions_value, 2),
                "roas": round(row.metrics.conversions_value / cost, 2) if cost > 0 else 0,
            })
        return keywords
    except Exception as e:
        logger.error(f"Quality score error: {e}")
        return [{"error": str(e)}]

# ============ AD ASSET PERFORMANCE ============

def fetch_ad_assets(date_from: str = None, date_to: str = None) -> list:
    """Fetch ad asset (headline, description) performance."""
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
                asset.text_asset.text,
                asset.type,
                ad_group_ad_asset_view.performance_label,
                ad_group_ad_asset_view.field_type,
                campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions
            FROM ad_group_ad_asset_view
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
                AND metrics.impressions > 0
            ORDER BY metrics.impressions DESC
        """
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        assets = []
        for row in response:
            assets.append({
                "text": row.asset.text_asset.text if row.asset.text_asset.text else "",
                "asset_type": row.asset.type_.name if row.asset.type_ else "",
                "performance_label": row.ad_group_ad_asset_view.performance_label.name if row.ad_group_ad_asset_view.performance_label else "",
                "field_type": row.ad_group_ad_asset_view.field_type.name if row.ad_group_ad_asset_view.field_type else "",
                "campaign": row.campaign.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(row.metrics.cost_micros / 1_000_000, 2),
                "conversions": round(row.metrics.conversions, 2),
                "ctr": round((row.metrics.clicks / row.metrics.impressions * 100), 2) if row.metrics.impressions > 0 else 0,
            })
        return assets
    except Exception as e:
        logger.error(f"Ad assets error: {e}")
        return [{"error": str(e)}]

# ============ CAMPAIGN IMPRESSION SHARE (Competition) ============

def fetch_campaign_competition(date_from: str = None, date_to: str = None) -> list:
    """Fetch campaign-level impression share and lost IS metrics."""
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
                campaign.name, campaign.status,
                metrics.search_impression_share,
                metrics.search_rank_lost_impression_share,
                metrics.search_budget_lost_impression_share,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
                AND campaign.status != 'REMOVED'
                AND campaign.advertising_channel_type = 'SEARCH'
            ORDER BY metrics.cost_micros DESC
        """
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        campaigns = []
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000
            campaigns.append({
                "campaign": row.campaign.name,
                "status": row.campaign.status.name,
                "impression_share": round(row.metrics.search_impression_share * 100, 1) if row.metrics.search_impression_share else 0,
                "lost_is_rank": round(row.metrics.search_rank_lost_impression_share * 100, 1) if row.metrics.search_rank_lost_impression_share else 0,
                "lost_is_budget": round(row.metrics.search_budget_lost_impression_share * 100, 1) if row.metrics.search_budget_lost_impression_share else 0,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(cost, 2),
                "conversions": round(row.metrics.conversions, 2),
                "conversion_value": round(row.metrics.conversions_value, 2),
                "roas": round(row.metrics.conversions_value / cost, 2) if cost > 0 else 0,
            })
        return campaigns
    except Exception as e:
        logger.error(f"Campaign competition error: {e}")
        return [{"error": str(e)}]

# ============ DEVICE PERFORMANCE ============

def fetch_device_performance(date_from: str = None, date_to: str = None) -> list:
    """Fetch performance by device type."""
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
                segments.device,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value,
                metrics.ctr, metrics.average_cpc
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
                AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        device_data = {}
        for row in response:
            device = row.segments.device.name
            if device not in device_data:
                device_data[device] = {"device": device, "impressions": 0, "clicks": 0, "cost": 0, "conversions": 0, "conversion_value": 0}
            d = device_data[device]
            d["impressions"] += row.metrics.impressions
            d["clicks"] += row.metrics.clicks
            d["cost"] += row.metrics.cost_micros / 1_000_000
            d["conversions"] += row.metrics.conversions
            d["conversion_value"] += row.metrics.conversions_value
        result = []
        for d in device_data.values():
            d["cost"] = round(d["cost"], 2)
            d["conversions"] = round(d["conversions"], 2)
            d["conversion_value"] = round(d["conversion_value"], 2)
            d["ctr"] = round((d["clicks"] / d["impressions"] * 100), 2) if d["impressions"] > 0 else 0
            d["avg_cpc"] = round(d["cost"] / d["clicks"], 2) if d["clicks"] > 0 else 0
            d["roas"] = round(d["conversion_value"] / d["cost"], 2) if d["cost"] > 0 else 0
            result.append(d)
        return sorted(result, key=lambda x: x["cost"], reverse=True)
    except Exception as e:
        logger.error(f"Device performance error: {e}")
        return [{"error": str(e)}]

# ============ HOURLY PERFORMANCE ============

def fetch_hourly_performance(date_from: str = None, date_to: str = None) -> list:
    """Fetch performance by hour of day."""
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
                segments.hour,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
                AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
        hourly = {}
        for row in response:
            h = row.segments.hour
            if h not in hourly:
                hourly[h] = {"hour": h, "impressions": 0, "clicks": 0, "cost": 0, "conversions": 0, "conversion_value": 0}
            d = hourly[h]
            d["impressions"] += row.metrics.impressions
            d["clicks"] += row.metrics.clicks
            d["cost"] += row.metrics.cost_micros / 1_000_000
            d["conversions"] += row.metrics.conversions
            d["conversion_value"] += row.metrics.conversions_value
        result = []
        for d in sorted(hourly.values(), key=lambda x: x["hour"]):
            d["cost"] = round(d["cost"], 2)
            d["conversions"] = round(d["conversions"], 2)
            d["conversion_value"] = round(d["conversion_value"], 2)
            d["roas"] = round(d["conversion_value"] / d["cost"], 2) if d["cost"] > 0 else 0
            result.append(d)
        return result
    except Exception as e:
        logger.error(f"Hourly performance error: {e}")
        return [{"error": str(e)}]

# ============ GSC PAGE PERFORMANCE ============

def fetch_gsc_pages(date_from: str = None, date_to: str = None, limit: int = 30) -> list:
    """Fetch Search Console data by page."""
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
            "startDate": date_from, "endDate": date_to,
            "dimensions": ["page"],
            "rowLimit": limit, "dataState": "final",
        }
        response = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=request).execute()
        rows = []
        for row in response.get("rows", []):
            rows.append({
                "page": row["keys"][0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            })
        return rows
    except Exception as e:
        logger.error(f"GSC pages error: {e}")
        return [{"error": str(e)}]

# ============ GA4 LANDING PAGE PERFORMANCE ============

def fetch_ga4_landing_pages(date_from: str = None, date_to: str = None) -> list:
    """Fetch GA4 landing page performance."""
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
            dimensions=[Dimension(name="landingPage")],
            metrics=[
                Metric(name="sessions"), Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"), Metric(name="ecommercePurchases"),
                Metric(name="totalRevenue"),
            ],
            limit=30,
        )
        response = client.run_report(request)
        pages = []
        for row in response.rows:
            pages.append({
                "page": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
                "bounce_rate": round(float(row.metric_values[1].value) * 100, 1),
                "avg_duration": round(float(row.metric_values[2].value), 1),
                "purchases": int(row.metric_values[3].value),
                "revenue": round(float(row.metric_values[4].value), 2),
            })
        return sorted(pages, key=lambda x: x["sessions"], reverse=True)
    except Exception as e:
        logger.error(f"GA4 landing pages error: {e}")
        return [{"error": str(e)}]

