#!/usr/bin/env python3
"""
Geocoder CLI tool - Converts location names to latitude/longitude coordinates
Uses OpenStreetMap Nominatim API (free and open source)
"""

import sys
import requests
import json


def geocode_location(location_name):
    """Get latitude and longitude for a location name using Nominatim API"""
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {"q": location_name, "format": "json", "limit": 1}

    headers = {"User-Agent": "MapsProgCLI/1.0 (https://github.com/user/repo)"}

    try:
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()

        data = response.json()

        if not data:
            print(f"No results found for: {location_name}")
            return None

        first_result = data[0]
        lat = first_result["lat"]
        lon = first_result["lon"]
        display_name = first_result["display_name"]

        return {"latitude": lat, "longitude": lon, "display_name": display_name}

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to geocoding service: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing response: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python geocoder.py <location>")
        print("Example: python geocoder.py 'Paris, France'")
        sys.exit(1)

    location = " ".join(sys.argv[1:])
    result = geocode_location(location)

    if result:
        print(f"Location: {result['display_name']}")
        print(f"Latitude: {result['latitude']}")
        print(f"Longitude: {result['longitude']}")


if __name__ == "__main__":
    main()
