"""Test profile location schema normalization."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_location_columns_exist():
    """Test that location_lat and location_lon columns exist in profile."""
    from database import Database

    profile = Database.get_profile()
    assert profile is not None
    assert 'location_lat' in profile, "location_lat not in profile"
    assert 'location_lon' in profile, "location_lon not in profile"
    print("✓ location_lat and location_lon exist in profile")


def test_get_location():
    """Test Database.get_location() returns structured location."""
    from database import Database

    loc = Database.get_location()
    assert isinstance(loc, dict)
    assert 'lat' in loc
    assert 'lon' in loc
    print(f"✓ get_location() returns: {loc}")


def test_update_location():
    """Test Database.update_location() stores values correctly."""
    from database import Database

    Database.update_location(-6.48, 108.44)
    loc = Database.get_location()
    assert loc['lat'] == -6.48, f"Expected -6.48, got {loc['lat']}"
    assert loc['lon'] == 108.44, f"Expected 108.44, got {loc['lon']}"
    print("✓ update_location() stores values correctly")


def test_location_not_in_context():
    """Test that location is not stored in context JSON."""
    from database import Database

    Database.update_location(-6.48, 108.44)
    ctx = Database.get_context()
    assert 'location' not in ctx, f"Location should not be in context: {ctx}"
    print("✓ Location is not in context JSON")


def test_update_profile_location():
    """Test that update_profile handles location_lat/location_lon."""
    from database import Database

    Database.update_profile({'location_lat': -7.25, 'location_lon': 112.75})
    profile = Database.get_profile()
    assert profile['location_lat'] == -7.25
    assert profile['location_lon'] == 112.75
    print("✓ update_profile handles location columns")


def test_migration_from_context():
    """Test migration moves location from context JSON to columns."""
    from database import Database, get_engine, _migrate_add_location_columns
    from sqlalchemy import text

    engine = get_engine()

    # Simulate old schema: location in context JSON
    with engine.connect() as conn:
        conn.execute(text(
            "UPDATE profiles SET location_lat = NULL, location_lon = NULL, "
            "context = :ctx"
        ), {'ctx': json.dumps({
            'location': {'lat': -8.5, 'lon': 115.2},
            'other_key': 'preserved'
        })})
        conn.commit()

    # Run migration
    _migrate_add_location_columns(engine)

    # Verify migration
    loc = Database.get_location()
    assert loc['lat'] == -8.5, f"Expected -8.5, got {loc['lat']}"
    assert loc['lon'] == 115.2, f"Expected 115.2, got {loc['lon']}"

    ctx = Database.get_context()
    assert 'location' not in ctx, "Location should be removed from context"
    assert ctx.get('other_key') == 'preserved', "Other context data should be preserved"
    print("✓ Migration from context JSON works correctly")


if __name__ == "__main__":
    try:
        test_location_columns_exist()
        test_get_location()
        test_update_location()
        test_location_not_in_context()
        test_update_profile_location()
        test_migration_from_context()
        print("\n" + "=" * 50)
        print("✅ ALL LOCATION SCHEMA TESTS PASSED")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
