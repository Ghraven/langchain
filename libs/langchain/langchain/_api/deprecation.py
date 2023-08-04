"""Helper functions for deprecating parts of the LangChain API.

This module was adapted from matplotlibs _api/deprecation.py module:

https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/_api/deprecation.py

.. warning::

    This module is for internal use only.  Do not use it in your own code.
    We may change the API at any time with no warning.
"""

import contextlib
import functools
import inspect
import warnings
from typing import Any, Callable, Generator, Optional, TypeVar


class LangChainDeprecationWarning(DeprecationWarning):
    """A class for issuing deprecation warnings for LangChain users."""


def _warn_deprecated(
    since: str,
    *,
    message: str = "",
    name: str = "",
    alternative: str = "",
    pending: bool = False,
    obj_type: str = "",
    addendum: str = "",
    removal: str = "",
) -> None:
    """Display a standardized deprecation.

    Arguments:
        since : str
            The release at which this API became deprecated.
        message : str, optional
            Override the default deprecation message. The %(since)s,
            %(name)s, %(alternative)s, %(obj_type)s, %(addendum)s,
            and %(removal)s format specifiers will be replaced by the
            values of the respective arguments passed to this function.
        name : str, optional
            The name of the deprecated object.
        alternative : str, optional
            An alternative API that the user may use in place of the
            deprecated API. The deprecation warning will tell the user
            about this alternative if provided.
        pending : bool, optional
            If True, uses a PendingDeprecationWarning instead of a
            DeprecationWarning. Cannot be used together with removal.
        obj_type : str, optional
            The object type being deprecated.
        addendum : str, optional
            Additional text appended directly to the final message.
        removal : str, optional
            The expected removal version. With the default (an empty
            string), a removal version is automatically computed from
            since. Set to other Falsy values to not schedule a removal
            date. Cannot be used together with pending.
    """
    if pending and removal:
        raise ValueError("A pending deprecation cannot have a scheduled removal")

    if not pending:
        if not removal:
            removal = f"in {removal}" if removal else "within ?? minor releases"
            raise NotImplementedError(
                f"Need to determine which default deprecation schedule to use. {removal}"
            )
        else:
            removal = f"in {removal}"

    if not message:
        message = ""

        if obj_type:
            message += f"The {obj_type} `{name}`"
        else:
            message += f"`{name}`"

        if pending:
            message += " will be deprecated in a future version"
        else:
            message += f" was deprecated in LangChain {since}"

            if removal:
                message += f" and will be removed {removal}"

        if alternative:
            message += f". Use {alternative} instead."

        if addendum:
            message += f" {addendum}"

    warning_cls = PendingDeprecationWarning if pending else LangChainDeprecationWarning
    warning = warning_cls(message)
    warnings.warn(warning, category=LangChainDeprecationWarning, stacklevel=2)


# PUBLIC API


T = TypeVar("T")


def deprecated(
    since: str,
    *,
    message: str = "",
    name: str = "",
    alternative: str = "",
    pending: bool = False,
    obj_type: Optional[str] = None,
    addendum: str = "",
    removal: str = "",
) -> Callable[[T], T]:
    """Decorator to mark a function, a class, or a property as deprecated.

    When deprecating a classmethod, a staticmethod, or a property, the
    ``@deprecated`` decorator should go *under* ``@classmethod`` and
    ``@staticmethod`` (i.e., `deprecated` should directly decorate the
    underlying callable), but *over* ``@property``.

    When deprecating a class ``C`` intended to be used as a base class in a
    multiple inheritance hierarchy, ``C`` *must* define an ``__init__`` method
    (if ``C`` instead inherited its ``__init__`` from its own base class, then
    ``@deprecated`` would mess up ``__init__`` inheritance when installing its
    own (deprecation-emitting) ``C.__init__``).

    Parameters are the same as for `warn_deprecated`, except that *obj_type*
    defaults to 'class' if decorating a class, 'attribute' if decorating a
    property, and 'function' otherwise.

    Arguments:
        since : str
            The release at which this API became deprecated.
        message : str, optional
            Override the default deprecation message. The %(since)s,
            %(name)s, %(alternative)s, %(obj_type)s, %(addendum)s,
            and %(removal)s format specifiers will be replaced by the
            values of the respective arguments passed to this function.
        name : str, optional
            The name of the deprecated object.
        alternative : str, optional
            An alternative API that the user may use in place of the
            deprecated API. The deprecation warning will tell the user
            about this alternative if provided.
        pending : bool, optional
            If True, uses a PendingDeprecationWarning instead of a
            DeprecationWarning. Cannot be used together with removal.
        obj_type : str, optional
            The object type being deprecated.
        addendum : str, optional
            Additional text appended directly to the final message.
        removal : str, optional
            The expected removal version. With the default (an empty
            string), a removal version is automatically computed from
            since. Set to other Falsy values to not schedule a removal
            date. Cannot be used together with pending.

    Examples
    --------

        .. code-block:: python

            @deprecated('1.4.0')
            def the_function_to_deprecate():
                pass
    """

    def deprecate(
        obj: Any,
        *,
        _obj_type: Optional[str] = obj_type,
        _name: Optional[str] = name,
        _message: Optional[str] = message,
        _alternative: str = alternative,
        _pending: bool = pending,
        _addendum: str = addendum,
    ):
        """Implementation of the decorator returned by `deprecated`."""
        if isinstance(obj, type):
            if _obj_type is None:
                _obj_type = "class"
            func = obj.__init__
            _name = _name or obj.__name__
            old_doc = obj.__doc__

            def finalize(wrapper: Any, new_doc: str) -> type:  # type: ignore
                """Finalize the deprecation of a class."""
                try:
                    obj.__doc__ = new_doc
                except AttributeError:  # Can't set on some extension objects.
                    pass
                obj.__init__ = functools.wraps(obj.__init__)(wrapper)
                return obj

        elif isinstance(obj, property):
            if _obj_type is None:
                _obj_type = "attribute"
            func = None
            _name = _name or obj.fget.__name__
            old_doc = obj.__doc__

            class _deprecated_property(type(obj)):
                """A deprecated property."""

                def __get__(self, instance, owner=None):  # type: ignore
                    if instance is not None or owner is not None:
                        emit_warning()
                    return super().__get__(instance, owner)

                def __set__(self, instance, value):  # type: ignore
                    if instance is not None:
                        emit_warning()
                    return super().__set__(instance, value)

                def __delete__(self, instance):  # type: ignore
                    if instance is not None:
                        emit_warning()
                    return super().__delete__(instance)

                def __set_name__(self, owner, set_name):  # type: ignore
                    nonlocal _name
                    if _name == "<lambda>":
                        _name = set_name

            def finalize(_, new_doc: str):  # type: ignore
                """Finalize the property."""
                return _deprecated_property(
                    fget=obj.fget, fset=obj.fset, fdel=obj.fdel, doc=new_doc
                )

        else:
            if _obj_type is None:
                _obj_type = "function"
            func = obj
            _name = _name or obj.__name__
            old_doc = func.__doc__

            def finalize(wrapper, new_doc):
                """Finalize the function."""
                wrapper = functools.wraps(func)(wrapper)
                wrapper.__doc__ = new_doc
                return wrapper

        def emit_warning() -> None:
            """Emit the warning."""
            _warn_deprecated(
                since,
                message=_message,
                name=_name,
                alternative=_alternative,
                pending=_pending,
                obj_type=_obj_type,
                addendum=_addendum,
                removal=removal,
            )

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrap the function."""
            emit_warning()
            return func(*args, **kwargs)

        old_doc = inspect.cleandoc(old_doc or "").strip("\n")

        if not old_doc:
            new_doc = f"[*Deprecated*]"
        else:
            new_doc = f"[*Deprecated*]  {old_doc}"

        return finalize(wrapper, new_doc)

    return deprecate


@contextlib.contextmanager
def suppress_langchain_deprecation_warning() -> Generator[None, None, None]:
    """Context manager to suppress LangChainDeprecationWarning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LangChainDeprecationWarning)
        yield
