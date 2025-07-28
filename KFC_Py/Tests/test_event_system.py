import pytest
from unittest.mock import Mock, MagicMock # נשתמש ב-Mock ליצירת Observers מדומים

from EventSystem import Publisher, Observer


# מחלקת Mock Observer פשוטה לבדיקה
class MockObserver(Observer):
    def __init__(self):
        self.updates_received = []

    def update(self, event_type: str, *args, **kwargs):
        self.updates_received.append({'event_type': event_type, 'args': args, 'kwargs': kwargs})


# Arrange: יצירת מופע Publisher ו-Observers מדומים עבור כל הטסטים
@pytest.fixture
def publisher():
    return Publisher()

@pytest.fixture
def observer1():
    return MockObserver()

@pytest.fixture
def observer2():
    return MockObserver()


# ──────────────────────────────────────────────────────────────────────────
#                          Publisher Basic Functionality Tests
# ──────────────────────────────────────────────────────────────────────────

def test_publisher_subscribe_sanity(publisher, observer1):
    """
    Sanity test: Verify an observer can subscribe successfully.
    """
    # Act
    publisher.subscribe(observer1)

    # Assert
    assert observer1 in publisher._subscribers
    assert len(publisher._subscribers) == 1


def test_publisher_subscribe_duplicate(publisher, observer1):
    """
    Edge case: Verify subscribing the same observer multiple times
    does not add it more than once.
    """
    # Arrange
    publisher.subscribe(observer1)

    # Act
    publisher.subscribe(observer1) # Try to subscribe again

    # Assert
    assert len(publisher._subscribers) == 1 # Should still only be one instance


def test_publisher_unsubscribe_sanity(publisher, observer1):
    """
    Sanity test: Verify an observer can unsubscribe successfully.
    """
    # Arrange
    publisher.subscribe(observer1)

    # Act
    publisher.unsubscribe(observer1)

    # Assert
    assert observer1 not in publisher._subscribers
    assert len(publisher._subscribers) == 0


def test_publisher_unsubscribe_non_existent(publisher, observer1):
    """
    Edge case: Verify unsubscribing a non-existent observer
    does not raise an error and list remains unchanged.
    """
    # Act
    publisher.unsubscribe(observer1) # Unsubscribe before subscribing

    # Assert
    assert observer1 not in publisher._subscribers
    assert len(publisher._subscribers) == 0


def test_publisher_notify_single_observer(publisher, observer1):
    """
    Sanity test: Verify notify calls update on a single subscribed observer
    with correct event details.
    """
    # Arrange
    publisher.subscribe(observer1)
    event_type = "test_event"
    args_data = (1, 2)
    kwargs_data = {"key": "value"}

    # Act
    publisher.notify(event_type, *args_data, **kwargs_data)

    # Assert
    assert len(observer1.updates_received) == 1
    update = observer1.updates_received[0]
    assert update['event_type'] == event_type
    assert update['args'] == args_data
    assert update['kwargs'] == kwargs_data


def test_publisher_notify_multiple_observers(publisher, observer1, observer2):
    """
    Sanity test: Verify notify calls update on multiple subscribed observers.
    """
    # Arrange
    publisher.subscribe(observer1)
    publisher.subscribe(observer2)
    event_type = "multi_event"

    # Act
    publisher.notify(event_type)

    # Assert
    assert len(observer1.updates_received) == 1
    assert observer1.updates_received[0]['event_type'] == event_type
    assert len(observer2.updates_received) == 1
    assert observer2.updates_received[0]['event_type'] == event_type


def test_publisher_notify_no_observers(publisher):
    """
    Edge case: Verify notify does not raise an error when no observers are subscribed.
    """
    # Act
    publisher.notify("no_one_listening_event") # Should run without error

    # Assert
    # No assertions on updates_received as no observers are present.
    # The test passes if no exception is raised.
    assert True


def test_publisher_notify_after_unsubscribe(publisher, observer1, observer2):
    """
    Sanity test: Verify notify does not call update on an unsubscribed observer.
    """
    # Arrange
    publisher.subscribe(observer1)
    publisher.subscribe(observer2)
    publisher.unsubscribe(observer1) # Unsubscribe observer1

    event_type = "after_unsubscribe_event"

    # Act
    publisher.notify(event_type)

    # Assert
    assert len(observer1.updates_received) == 0 # observer1 should not have received update
    assert len(observer2.updates_received) == 1
    assert observer2.updates_received[0]['event_type'] == event_type