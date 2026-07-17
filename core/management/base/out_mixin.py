"""
Thread-safe output handler for Django management commands with Rich support.

This module provides a mixin class that can be used to handle output messages in a
thread-safe manner for Django management commands. It ensures that output from multiple
threads doesn't get interleaved, leading to cleaner, more readable console output.

Includes optional Rich library support with ANSI fallback for enhanced terminal
formatting (colors, panels, tables) without requiring external dependencies.

Example:
    ```python
    from django.core.management.base import BaseCommand
    from .out_mixin import OutMixin

    class Command(OutMixin, BaseCommand):
        def handle(self, *args, **options):
            self.out("Starting process...")
            self.out_success("Task completed successfully!")

            # Rich components (with automatic ANSI fallback)
            table = self.Table(title="Results")
            table.add_column("ID")
            table.add_column("Status")
            table.add_row("1", "OK")
            self.Console.print(table)
    ```

"""

import logging
import os
import sys
import threading
from datetime import datetime
from shutil import get_terminal_size

from django.core.management.base import CommandError
from django.utils.functional import Promise
from django.utils.termcolors import colorize
from django.utils.translation import gettext as _

from core.utils.rich_with_fallback import (
    RICH_AVAILABLE,
    FallbackConsole,
    FallbackPanel,
    FallbackTable,
    FallbackText,
    RichConsole,
    RichPanel,
    RichTable,
    RichText,
    fallback_escape,
    fallback_track,
    rich_escape,
    rich_track,
)


class OutMixin:
    """
    A mixin class for handling output messages in the command line interface.
    Thread-safe version that prevents line interleaving.

    This class provides various methods for outputting messages to stdout and stderr
    with different styles (success, warning, error, notice). All output methods are
    thread-safe, ensuring that output from multiple threads doesn't get interleaved.

    Includes Rich library support with automatic ANSI fallback.

    Attributes:
        _output_lock (threading.RLock): Lock for synchronizing output operations.
        _output_paused (bool): Flag indicating if output is paused.
        stderr (file): Standard error stream.
        stdout (file): Standard output stream.
        style (object): Django style object for coloring output.
        OUT_SUCCESS (dict): Style settings for success messages.
        OUT_WARNING (dict): Style settings for warning messages.
        OUT_ERROR (dict): Style settings for error messages.
        OUT_NOTICE (dict): Style settings for notice messages.
        verbosity (int): Output verbosity level (0-3).
        Console: Rich Console instance (real or fallback).
        Text: Rich Text class (real or fallback).
        Panel: Rich Panel class (real or fallback).
        Table: Rich Table class (real or fallback).
        escape: Rich escape function (real or fallback).
    """

    # Class-level aliases for the Rich UI component *classes*.
    #
    # These three names (``Panel``, ``Table``, ``Text``) are assigned at class scope so
    # that static analyzers can resolve the real ``rich.*`` constructor signatures at
    # every call site - including ``self.Panel(renderable, expand=False)``,
    # ``self.Table(title=...)``, and so on. Instance-level rebinding still happens
    # inside ``_setup_rich`` when the ANSI fallback path is selected; the fallback
    # classes in ``core.utils.rich_with_fallback`` are expected to honor the same
    # constructor surface, so runtime behavior is unchanged.
    #
    # ``Console`` and ``escape`` intentionally stay instance-bound: ``Console`` is built
    # lazily via ``_build_rich_console()`` with environment-dependent settings (PyCharm
    # detection, NO_COLOR opt out, terminal width floor) and ``escape`` is a function
    # reference, neither of which benefits from class-level promotion.
    Panel = RichPanel
    Table = RichTable
    Text = RichText

    def __init__(
        self, stdout=None, stderr=None, no_color=False, force_color=False, use_rich=True
    ):
        """
        Initialize the OutMixin.

        Args:
            stdout (file, optional): Standard output stream. Defaults to None.
            stderr (file, optional): Standard error stream. Defaults to None.
            no_color (bool, optional): If True, don't use colors.
                Defaults to False.
            force_color (bool, optional): If True, force color output.
                Defaults to False.
            use_rich (bool, optional): If True, try to use Rich library.
                Defaults to True.
        """
        self._output_lock = threading.RLock()

        self.logger = logging.getLogger(__name__)
        self._output_paused = None
        self.stderr = None
        self.stdout = None
        self.style = None
        self.verbosity = 1
        self.OUT_SUCCESS = None
        self.OUT_WARNING = None
        self.OUT_ERROR = None
        self.OUT_NOTICE = None

        self._setup_rich(use_rich)

        super().__init__(stdout, stderr, no_color, force_color)

    def _setup_rich(self, use_rich):
        """Setup Rich library or fallback.

        When Rich is available and enabled, the Console is instantiated with settings
        that stay consistent across the three environments that hit us in practice:

          * A real TTY (local shell, ssh): Rich's own auto-detection is correct; nothing
            to override.
          * PyCharm's Run / Debug console: stdout is captured, so Rich probes
            ``is_terminal=False`` and collapses width to 80 columns with
            color_system=None. We detect PyCharm via the ``PYCHARM_HOSTED`` env var it
            exports to every child process and force ``force_terminal=True`` +
            ``color_system='truecolor'``. Width is read from the terminal if PyCharm
            exposes it, otherwise floored at 220 so tables do not fold into unreadable
            columns.
          * Output piped to a file (``> out.log``): same ``is_terminal=False`` signal,
            but here we *want* plain output without ANSI. PYCHARM_HOSTED is not set when
            the shell runs the command, so this case keeps the auto behavior. Under
            PyCharm with an explicit redirection the caller can still set ``NO_COLOR=1``
            to opt out.

        Args:
            use_rich: If True and Rich is available, use Rich library.
        """
        if use_rich and RICH_AVAILABLE:
            self._use_rich = True
            self.Console = self._build_rich_console()
            self.Text = RichText
            self.Panel = RichPanel
            self.Table = RichTable
            self.escape = rich_escape
        else:
            self._use_rich = False
            self.Console = FallbackConsole()
            self.Text = FallbackText
            self.Panel = FallbackPanel
            self.Table = FallbackTable
            self.escape = fallback_escape

    @staticmethod
    def _build_rich_console():
        """Instantiate a Rich Console tailored to the host environment.

        See ``_setup_rich`` for the rationale. Exposed as a standalone staticmethod so
        subclasses can override the construction without reimplementing the
        Rich/fallback dispatch.

        Returns:
            Configured RichConsole instance.
        """
        if os.environ.get("NO_COLOR") is not None:
            # Standard opt-out: user does not want color regardless of detection. Still
            # pick a reasonable width.
            return RichConsole(color_system=None)

        in_pycharm = os.environ.get("PYCHARM_HOSTED") == "1"
        if not in_pycharm:
            # Real terminals: Rich's autodetection is accurate.
            return RichConsole()

        # PyCharm Run / Debug console: force terminal mode and pick a width that
        # survives the capture. get_terminal_size may return the Run console's actual
        # width when "Emulate terminal" is on; fallback to 220 otherwise.
        detected = get_terminal_size(fallback=(220, 24)).columns
        return RichConsole(
            force_terminal=True,
            color_system="truecolor",
            width=max(detected, 220),
        )

    @property
    def has_rich(self):
        """Check if Rich library is being used.

        Returns:
            bool: True if using real Rich library.
        """
        return self._use_rich

    def set_verbosity(self, level):
        """
        Set the verbosity level for output.

        Args:
            level (int): Verbosity level from 0 to 3.
        """
        self.verbosity = max(0, min(3, level))

    def should_output(self, min_level):
        """
        Check if output should be displayed based on verbosity level.

        Args:
            min_level (int): Minimum verbosity level required for output.

        Returns:
            bool: True if output should be displayed, False otherwise.
        """
        return self.verbosity >= min_level

    def progress(self, iterable, total=None, description=None):
        """Iterate ``iterable`` while rendering a progress bar.

        Dispatches to ``rich.progress.track`` when Rich is enabled and to the project's
        ANSI fallback otherwise, mirroring the same Rich/fallback split used by
        ``Console``, ``Table`` and friends.

        Args:
            iterable: Sequence or iterator to walk.
            total: Total step count; required when ``iterable`` has no
                ``__len__``.
            description: Optional label printed alongside the bar.

        Returns:
            An iterator yielding the items of ``iterable``.
        """
        if self._use_rich:
            return rich_track(
                iterable,
                description=description or "",
                total=total,
                console=self.Console,
            )
        return fallback_track(iterable, description=description, total=total)

    def out(self, msg, keep_spaces=True, **kwargs):
        """
        Thread-safe output method.

        Acquires a lock before outputting the message to ensure that output from
        multiple threads doesn't get interleaved.

        Args:
            msg (str, Promise or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline messages
                when without_time=False or for messages with newlines. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
                is_success (bool): Style as a success message.
                is_warning (bool): Style as a warning message.
                is_error (bool): Style as an error message.
                without_time (bool): Don't include timestamp.
                no_nl (bool): Don't add newline at the end.
                colorize (dict): Custom colorize settings.
                min_verbosity (int): Minimum verbosity level to display this message.
        """
        min_verbosity = kwargs.pop("min_verbosity", 1)
        if not self.should_output(min_verbosity):
            return

        with self._output_lock:
            self._out_verbose_impl(msg, keep_spaces=keep_spaces, **kwargs)

    def out_thread_safe(self, msg, keep_spaces=True, **kwargs):
        """
        Alias for out() method for backward compatibility.

        Args:
            msg (str, Promise or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline messages.
            **kwargs: Additional keyword arguments for styling the output.
        """
        self.out(msg, keep_spaces=keep_spaces, **kwargs)

    def _out_verbose_impl(self, msg, keep_spaces=True, **kwargs):
        """Implementation of out_verbose without locking.

        This is the actual implementation of the output functionality, called by out
        after acquiring the lock.

        Args:
            msg (str or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline messages
                when without_time=False or for messages with newlines. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
                is_success (bool): Style as a success message.
                is_warning (bool): Style as a warning message.
                is_error (bool): Style as an error message.
                without_time (bool): Don't include timestamp.
                no_nl (bool): Don't add newline at the end.
                colorize (dict): Custom colorize settings.
        """
        # Convert lazy translation objects to strings
        if isinstance(msg, Promise):
            msg = str(msg)
        elif isinstance(msg, list):
            msg = [str(m) if isinstance(m, Promise) else m for m in msg]

        if self.logger:
            if kwargs.get("is_error"):
                self.logger.error(msg)
            elif kwargs.get("is_warning"):
                self.logger.warning(msg)
            elif kwargs.get("is_success"):
                self.logger.info(msg)
            else:
                self.logger.info(msg)

        time = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        messages = [msg] if not isinstance(msg, list) else msg
        str_time = f"> {time} : " if not kwargs.get("without_time") else ""
        spacing = (
            " " * len(str_time)
            if keep_spaces and not kwargs.get("without_time")
            else ""
        )
        output = self.stderr if kwargs.get("is_error") else self.stdout

        style_dict = {
            "is_success": ("OUT_SUCCESS", self.style.SUCCESS),
            "is_warning": ("OUT_WARNING", self.style.WARNING),
            "is_error": ("OUT_ERROR", self.style.ERROR),
            "colorize": ("colorize", None),
        }
        default_style = ("OUT_NOTICE", self.style.NOTICE)

        for i, msg in enumerate(messages):
            # Convert again in case msg was in a list
            if isinstance(msg, Promise):
                msg = str(msg)

            # Handle multiline messages within a single message
            if "\n" in str(msg) and keep_spaces:
                lines = str(msg).split("\n")
                styled_lines = []

                for line in lines:
                    styled_line = self._apply_styling(
                        line, style_dict, default_style, kwargs
                    )
                    styled_lines.append(styled_line)

                # First line gets the timestamp, subsequent lines get spacing
                prefix = str_time if i == 0 else spacing
                first_line = styled_lines[0]
                remaining_lines = styled_lines[1:]

                # Output first line with prefix
                ending = (
                    ""
                    if kwargs.get("no_nl")
                    and i == len(messages) - 1
                    and not remaining_lines
                    else "\n"
                )
                output.write(f"{prefix}{first_line}", ending=ending)

                # Output remaining lines with spacing
                for line_idx, line in enumerate(remaining_lines):
                    is_last_line = (
                        line_idx == len(remaining_lines) - 1 and i == len(messages) - 1
                    )
                    ending = "" if kwargs.get("no_nl") and is_last_line else "\n"
                    output.write(f"{spacing}{line}", ending=ending)
            else:
                # Single line message - apply styling
                prefix = str_time if i == 0 else spacing
                styled_msg = self._apply_styling(msg, style_dict, default_style, kwargs)
                ending = "" if kwargs.get("no_nl") and i == len(messages) - 1 else "\n"
                output.write(f"{prefix}{styled_msg}", ending=ending)

    def _apply_styling(self, text, style_dict, default_style, kwargs):
        """Apply appropriate styling to text.

        Args:
            text: Text to style.
            style_dict: Dictionary mapping kwargs to style attributes.
            default_style: Default style to use.
            kwargs: Keyword arguments with style flags.

        Returns:
            str: Styled text.
        """
        for style_kwarg, (style_attr, default_method) in style_dict.items():
            if kwargs.get(style_kwarg):
                if getattr(self, style_attr):
                    return colorize(text, **getattr(self, style_attr))
                else:
                    return (
                        default_method(text)
                        if default_method
                        else colorize(text, **kwargs.get(style_attr))
                    )

        # Apply default style
        if getattr(self, default_style[0]):
            return colorize(text, **getattr(self, default_style[0]))
        else:
            return default_style[1](text)

    # Original function kept for compatibility
    def out_verbose(self, msg, keep_spaces=True, **kwargs):
        """
        Alias for out_thread_safe() for backward compatibility.

        Args:
            msg (str or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline
                messages. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.

        Returns:
            The result of calling out_thread_safe.
        """
        self.out_thread_safe(msg, keep_spaces=keep_spaces, **kwargs)

    @staticmethod
    def abort(err):
        """
        Writes the error message to stderr and raises a CommandError with the same
        message.

        Args:
            err (str): Error message.

        Raises:
            CommandError: With the provided error message.
        """
        sys.stderr.write(_("[Error: {}]\n").format(err))
        raise CommandError(_(err))

    @staticmethod
    def out_silent(msg, **kwargs):
        """
        Writes the message to stderr only if 'is_error' is specified in kwargs.

        This method is useful for silent mode where only errors should be output.

        Args:
            msg (str): Message to output.
            **kwargs: Additional keyword arguments.
                is_error (bool): If True, output as error.
        """
        if bool(kwargs.get("is_error")):
            sys.stderr.write(_("[Error: {}]\n").format(msg))

    def out_option_on_or_off(self, option, description):
        """
        Writes the status of the specified option to stdout.

        Args:
            option (bool): Option status.
            description (str): Description of the option.
        """
        if option:
            self.out(_("[With option '{}']").format(description))
        else:
            self.out(_("[Without option '{}']").format(description))

    def out_success(self, msg, keep_spaces=True, **kwargs):
        """
        Writes the message to stdout with 'success' style.

        Args:
            msg (str, Promise or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline
                messages. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
        """
        self.out(msg, keep_spaces=keep_spaces, **{"is_success": True, **kwargs})

    def out_error(self, msg, keep_spaces=True, **kwargs):
        """
        Writes the message to stderr with 'error' style.

        Args:
            msg (str, Promise or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline
                messages. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
        """
        self.out(msg, keep_spaces=keep_spaces, **{"is_error": True, **kwargs})

    def out_warning(self, msg, keep_spaces=True, **kwargs):
        """
        Writes the message to stderr with 'warning' style.

        Args:
            msg (str, Promise or list): Message or list of messages to output.
            keep_spaces (bool): Keep spacing alignment for multiline
                messages. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
        """
        self.out(msg, keep_spaces=keep_spaces, **{"is_warning": True, **kwargs})

    # Verbosity-specific methods
    def out_verbose_low(self, msg, **kwargs):
        """
        Output message with low verbosity requirement (level 1).

        Args:
            msg (str): Message to output.
            **kwargs: Additional keyword arguments for styling.
        """
        self.out(msg, **{**kwargs, "min_verbosity": 1})

    def out_verbose_medium(self, msg, **kwargs):
        """
        Output message with medium verbosity requirement (level 2).

        Args:
            msg (str): Message to output.
            **kwargs: Additional keyword arguments for styling.
        """
        self.out(msg, **{**kwargs, "min_verbosity": 2})

    def out_verbose_high(self, msg, **kwargs):
        """
        Output message with high verbosity requirement (level 3).

        Args:
            msg (str): Message to output.
            **kwargs: Additional keyword arguments for styling.
        """
        self.out(msg, **{**kwargs, "min_verbosity": 3})

    def out_debug(self, msg, **kwargs):
        """
        Output debug message with the highest verbosity requirement (level 3).

        Args:
            msg (str): Message to output.
            **kwargs: Additional keyword arguments for styling.
        """
        self.out(msg, **{**kwargs, "min_verbosity": 3, "without_time": True})

    # Thread-safe versions with thread identification
    def thread_safe_out_error(self, message, keep_spaces=True, **kwargs):
        """
        Thread-safe version of self.out_error with thread identification.

        Adds thread identifier to the message before outputting it as an error.

        Args:
            message (str): Message to output.
            keep_spaces (bool): Keep spacing alignment for multiline
                messages. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
        """
        thread_id = threading.current_thread().name
        self.out_error(
            f"{_('[Thread {}]').format(thread_id)} {message}",
            keep_spaces=keep_spaces,
            **kwargs,
        )

    def thread_safe_out_warning(self, message, keep_spaces=True, **kwargs):
        """
        Thread-safe version of self.out_warning with thread identification.

        Adds thread identifier to the message before outputting it as a warning.

        Args:
            message (str): Message to output.
            keep_spaces (bool): Keep spacing alignment for multiline
                messages. Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
        """
        thread_id = threading.current_thread().name
        self.out_warning(
            f"{_('[Thread {}]').format(thread_id)} {message}",
            keep_spaces=keep_spaces,
            **kwargs,
        )

    def thread_safe_out_success(self, message, keep_spaces=True, **kwargs):
        """
        Thread-safe version of self.out_success with thread identification.

        Adds thread identifier to the message before outputting it as a success.

        Args:
            message (str): Message to output.
            keep_spaces (bool): Keep spacing alignment for multiline messages.
                                Defaults to True.
            **kwargs: Additional keyword arguments for styling the output.
        """
        thread_id = threading.current_thread().name
        self.out_success(
            f"{_('[Thread {}]').format(thread_id)} {message}",
            keep_spaces=keep_spaces,
            **kwargs,
        )
