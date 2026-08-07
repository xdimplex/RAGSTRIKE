"""``ragstrike.sdk.helpers`` -- stateful or I/O-adjacent reusable helpers.

Split from :mod:`ragstrike.sdk.utils` deliberately: everything in *this* package either does I/O
(``FileHelper``, ``JsonHelper.load_file``, ``YamlHelper.load_file``), carries state across calls
(``Timer``), or has externally observable side effects (``retry_async`` sleeps; the id generators
consume randomness). ``utils`` is the opposite -- pure functions over strings and numbers, safe to
call in a tight loop with no side effect other than their return value. If you are unsure which
package a new helper belongs in, ask whether it touches the filesystem, the clock, or a random
source: if yes, it belongs here.
"""

from ragstrike.sdk.helpers.files import FileHelper
from ragstrike.sdk.helpers.identifiers import new_short_id, new_uuid
from ragstrike.sdk.helpers.json_helper import JsonHelper
from ragstrike.sdk.helpers.retry import retry_async
from ragstrike.sdk.helpers.timer import Timer
from ragstrike.sdk.helpers.yaml_helper import YamlHelper

__all__ = [
    "FileHelper",
    "JsonHelper",
    "Timer",
    "YamlHelper",
    "new_short_id",
    "new_uuid",
    "retry_async",
]
