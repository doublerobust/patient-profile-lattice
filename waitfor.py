"""CSP-safe page waiting for the browser tests.

Playwright's page.wait_for_function() compiles its predicate with eval inside the
page. This viewer serves `Content-Security-Policy: script-src 'self'` without
'unsafe-eval', so that compilation intermittently raises

    EvalError: Evaluating a string as JavaScript violates the following
    Content Security Policy directive ... 'unsafe-eval' is not an allowed source

and the failure surfaces as a timeout instead of an assertion. It passes in
isolation and fails under load, which is exactly how it wasted three runs.

page.evaluate() sends the arrow function over CDP (Runtime.callFunctionOn) and
is not subject to the page's eval restriction, so polling it is safe here.

Usage:
    wait_for(page, "window.lattice && lattice.ready")
    wait_for(page, "() => window.clinical3d?.ready")
"""
import time

_WRAPPER = "(__arg) => { const f = (%s); return typeof f === 'function' ? !!f(__arg) : !!f; }"


def wait_for(page_or_frame, expression, timeout=30000, poll=0.05, arg=None):
    fn = _WRAPPER % (expression.strip(),)
    deadline = time.time() + timeout / 1000.0
    last = None
    while time.time() < deadline:
        try:
            if page_or_frame.evaluate(fn, arg):
                return True
            last = None
        except Exception as exc:  # transient navigation / not-yet-defined
            last = exc
        time.sleep(poll)
    detail = (" last error: %r" % (last,)) if last else ""
    raise AssertionError("timed out after %sms waiting for: %s%s" % (timeout, expression, detail))
