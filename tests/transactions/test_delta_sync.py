import json
import time
from tests.util.base import add_fake_message, add_fake_thread

__all__ = ['api_client', 'db', 'thread']


def get_cursor(api_client, timestamp):
    cursor_response = api_client.post_data('/delta/generate_cursor',
                                           {'start': timestamp})
    return json.loads(cursor_response.data)['cursor']


def test_invalid_input(api_client):
    cursor_response = api_client.post_data('/delta/generate_cursor',
                                           {'start': "I'm not a timestamp!"})
    assert cursor_response.status_code == 400

    sync_response = api_client.client.get(api_client.full_path(
        '/delta?cursor={}'.format('fake cursor')))
    assert sync_response.status_code == 400


def test_events_are_condensed(api_client, message):
    """Test that multiple revisions of the same object are rolled up in the
    delta response."""
    ts = int(time.time() + 22)
    cursor = get_cursor(api_client, ts)

    # Modify a message, then modify it again
    message_id = api_client.get_data('/messages/')[0]['id']
    message_path = '/messages/{}'.format(message_id)
    api_client.put_data(message_path, {'unread': True})
    api_client.put_data(message_path, {'unread': False})
    api_client.put_data(message_path, {'unread': True})

    # Check that successive modifies are condensed.
    sync_data = api_client.get_data('/delta?cursor={}'.format(cursor))
    assert len(sync_data['deltas']) == 1
    delta = sync_data['deltas'][0]
    assert (delta['object'] == 'message' and
            delta['event'] == 'modify')
    assert delta['attributes']['unread'] is True


def test_handle_missing_objects(api_client, db, thread, default_namespace):
    ts = int(time.time() + 22)
    cursor = get_cursor(api_client, ts)

    messages = []
    for _ in range(100):
        messages.append(add_fake_message(db.session, default_namespace.id,
                                         thread))
    for message in messages:
        db.session.delete(message)
    db.session.commit()
    sync_data = api_client.get_data('/delta?cursor={}&exclude_types=thread'.
                                    format(cursor))
    assert len(sync_data['deltas']) == 100
    assert all(delta['event'] == 'delete' for delta in sync_data['deltas'])
