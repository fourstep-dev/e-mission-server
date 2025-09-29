# emission/analysis/result/user_stats.py

import logging
import requests
import pymongo
import arrow
from typing import Optional, Dict, Any
import emission.storage.timeseries.abstract_timeseries as esta
import emission.core.wrapper.user as ecwu
import emission.analysis.config as eac


def notify_fourstep_of_first_trip(user_id) -> bool:
    """
    Notify Fourstep API when user completes their first trip.
    Returns True if successful, False otherwise.
    """

    try:
        fourstep_auth_token = eac.get_config()["fourstep.auth_token"]
        if not fourstep_auth_token:
            logging.warning("fourstep.auth_token not configured, skipping notification")
            return False
        
        requests.post(
            url="https://fourstep.dev/api/user/onboard",
            json={"uuid": str(user_id)},
            headers={
                "Authorization": "Bearer " + fourstep_auth_token,
            },
            timeout=5,
        )
        logging.info(f"Successfully notified Fourstep of first trip for user {user_id}")
        return True
    
    except Exception as e:
        logging.error(
            f"Failed to notify Fourstep of first trip for user {user_id}: {e}"
        )
        return False

def update_upload_timestamp(user_id: str, stat_name: str, ts: float) -> None:
    """
    Updates the upload timestamps in the profile

    :param user_id: The user's UUID
    :type user_id: str
    :param stat_name: The field name that is updated
    :type stat_name: str
    :param ts: The timestamp to store (may not always be 'now')
    :type ts: float
    :return: None
    """
    update_data = {
        stat_name: ts
    }
    update_user_profile(user_id, update_data)

def update_last_call_timestamp(user_id: str, call_path: str) -> Optional[int]:
    """
    Updates the user profile with server call starts

    :param user_id: The user's UUID
    :type user_id: str
    :param call_path: Can be used to store different call stats
    :type ts: str
    :return: None
    """
    logging.debug(f"update_last_call_timestamp called with: {user_id=}, {call_path=}")
    now = arrow.now().timestamp()
    update_data = {
        "last_call_ts": now
    }
    if "usercache" in call_path:
        update_data["last_sync_ts"] = now
    if "usercache/put" in call_path:
        update_data["last_put_ts"] = now
    if call_path == "/pipeline/get_range_ts":
        update_data["last_diary_fetch_ts"] = now
    update_user_profile(user_id, update_data)

def update_user_profile(user_id: str, data: Dict[str, Any]) -> None:
    """
    Updates the user profile with the provided data.

    :param user_id: The UUID of the user.
    :type user_id: str
    :param data: The data to update in the user profile.
    :type data: Dict[str, Any]
    :return: None
    """
    user = ecwu.User.fromUUID(user_id)
    # Check for first trip notification BEFORE updating
    new_trips = data.get("total_trips")
    if new_trips is not None and new_trips > 0:
        user_profile = user.getProfile()
        prev_trips = user_profile.get("total_trips", 0)

        # Only notify if transitioning from 0 to positive trips
        if prev_trips == 0:
            notify_fourstep_of_first_trip(user_id)

    user.update(data)
    logging.debug(f"User profile updated with data: {data}")
    logging.debug(f"New profile: {user.getProfile()}")


def get_and_store_pipeline_dependent_user_stats(user_id: str, trip_key: str) -> None:
    """
    Aggregates and stores pipeline dependent into the user profile.
    These are statistics based on analysed data such as trips or labels.

    :param user_id: The UUID of the user.
    :type user_id: str
    :param trip_key: The key representing the trip data in the time series.
    :type trip_key: str
    :return: None
    """
    try:
        logging.info(f"Starting get_and_store_pipeline_dependent_user_stats for user_id: {user_id}, trip_key: {trip_key}")

        ts = esta.TimeSeries.get_time_series(user_id)
        start_ts_result = ts.get_first_value_for_field(trip_key, "data.start_ts", pymongo.ASCENDING)
        start_ts = None if start_ts_result == -1 else start_ts_result

        end_ts_result = ts.get_first_value_for_field(trip_key, "data.end_ts", pymongo.DESCENDING)
        end_ts = None if end_ts_result == -1 else end_ts_result

        total_trips = ts.find_entries_count(key_list=["analysis/confirmed_trip"])
        labeled_trips = ts.find_entries_count(
            key_list=["analysis/confirmed_trip"],
            extra_query_list=[{'data.user_input': {'$ne': {}}}]
        )

        logging.info(f"Total trips: {total_trips}, Labeled trips: {labeled_trips}")
        update_data = {
            "pipeline_range": {
                "start_ts": start_ts,
                "end_ts": end_ts
            },
            "total_trips": total_trips,
            "labeled_trips": labeled_trips,
        }

        logging.info(f"user_id type: {type(user_id)}")
        update_user_profile(user_id, update_data)

        logging.debug("User profile updated successfully.")

    except Exception as e:
        logging.error(f"Error in get_and_store_dependent_user_stats for user_id {user_id}: {e}")

