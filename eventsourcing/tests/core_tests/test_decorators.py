from unittest.case import TestCase
from uuid import uuid4

from mock import mock

from eventsourcing.domain.model.decorators import mutator, retry, subscribe_to
from eventsourcing.domain.model.events import assert_event_handlers_empty, \
    EventHandlersNotEmptyError, publish
from eventsourcing.example.domainmodel import Example
from eventsourcing.utils.topic import get_topic


class TestDecorators(TestCase):

    def test_retry_without_arg(self):
        # Check docstrings of decorated functions.
        def func(*args):
            """func docstring"""
            return 1

        def func_raises(exc=Exception):
            """func_raises docstring"""
            raise exc

        self.assertEqual(retry(func).__doc__, func.__doc__)
        self.assertEqual(retry()(func).__doc__, func.__doc__)
        self.assertEqual(retry(func_raises).__doc__, func_raises.__doc__)
        self.assertEqual(retry()(func_raises).__doc__, func_raises.__doc__)

        # Check func returns correctly after it is decorated.
        self.assertEqual(retry(func)(), 1)
        self.assertEqual(retry()(func)(), 1)

        # Check func raises correctly after it is decorated.
        with self.assertRaises(Exception):
            retry(func_raises, wait=0)()
        with self.assertRaises(Exception):
            retry(wait=0)(func_raises)()

        with self.assertRaises(NotImplementedError):
            retry(func_raises, wait=0)(NotImplementedError)
        with self.assertRaises(NotImplementedError):
            retry(wait=0)(func_raises)(NotImplementedError)

        with self.assertRaises(NotImplementedError):
            retry(func_raises, wait=0, max_attempts=0)(NotImplementedError)
        with self.assertRaises(NotImplementedError):
            retry(wait=0, max_attempts=0)(func_raises)(NotImplementedError)

        # Check TypeError is raised if args have incorrect values.
        with self.assertRaises(TypeError):
            retry(max_attempts='')  # needs to be an int

        with self.assertRaises(TypeError):
            retry(exc=TestCase)  # need to be subclass of Exception (single value)

        with self.assertRaises(TypeError):
            retry(exc=(TestCase,))  # need to be subclass of Exception (tuple)

        with self.assertRaises(TypeError):
            retry(wait='')  # needs to be a float

    def test_mutate_without_arg(self):
        # Define an entity class, and event class, and a mutator function.

        class Entity(object): pass

        class Event(object): pass

        @mutator
        def mutate_entity(initial, event):
            """Docstring for function mutate()."""
            raise NotImplementedError()

        # Check the function looks like the original.
        self.assertEqual(mutate_entity.__doc__, "Docstring for function mutate().")

        # Check it is capable of registering event handlers.
        @mutate_entity.register(Event)
        def mutate_with_event(initial, event):
            return Entity()

        # Check it dispatches on type of last arg.
        self.assertIsInstance(mutate_entity(None, Event()), Entity)

        # Check it handles unregistered types.
        with self.assertRaises(NotImplementedError):
            mutate_entity(None, None)

    def test_mutate_with_arg(self):
        # Define an entity class, and event class, and a mutator function.

        class Entity(object): pass

        class Event(object): pass

        @mutator(Entity)
        def mutate_entity(initial, event):
            """Docstring for function mutate()."""
            raise NotImplementedError()

        # Check the function looks like the original.
        self.assertEqual(mutate_entity.__doc__, "Docstring for function mutate().")

        # Check it is capable of registering event handlers.
        @mutate_entity.register(Event)
        def mutate_with_event(initial, event):
            return initial()

        # Check it dispatches on type of last arg.
        self.assertIsInstance(mutate_entity(None, Event()), Entity)

        # Check it handles unregistered types.
        with self.assertRaises(NotImplementedError):
            mutate_entity(None, None)

    def test_subscribe_to_decorator(self):
        entity_id1 = uuid4()
        event1 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1, b=2
        )
        event2 = Example.Discarded(
            originator_id=entity_id1,
            originator_version=1,
        )
        handler = mock.Mock()

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        @subscribe_to(Example.Created)
        def test_handler(e):
            """Doc string"""
            handler(e)

        # Check the decorator doesn't mess with the function doc string.
        self.assertEqual('Doc string', test_handler.__doc__)

        # Check can fail to assert event handlers empty.
        self.assertRaises(EventHandlersNotEmptyError, assert_event_handlers_empty)

        # Check event is received when published individually.
        publish(event1)
        handler.assert_called_once_with(event1)

        # Check event of wrong type is not received.
        handler.reset_mock()
        publish(event2)
        self.assertFalse(handler.call_count)

        # Check a list of events can be filtered.
        handler.reset_mock()
        publish([event1, event2])
        handler.assert_called_once_with(event1)

        handler.reset_mock()
        publish([event1, event1])
        self.assertEqual(2, handler.call_count)

        handler.reset_mock()
        publish([event2, event2])
        self.assertEqual(0, handler.call_count)
