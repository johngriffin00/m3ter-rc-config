"""One lego brick.

A Step has a name and a run(ctx) method. That is the whole contract: the
orchestrator builds a list of steps and runs them in order, each one reading
ctx.snapshot / ctx.state and writing its results back into ctx.state.

Two conventions every step follows, both lifted from the m3sh workflows:

  * Look before you create. m3sh guards each create with
    ExternalMappingExistsForSystem; here each m3ter step calls find_existing()
    first and only creates when that returns nothing, so re-running an order
    is safe (idempotent).
  * Dry run is honoured inside the step. When ctx.dry_run is set, a step
    still READS m3ter (so the find-before-create check is real) but prints
    the payload it would have posted instead of posting it.
"""
import json
from types import SimpleNamespace


class Step:
    name = 'unnamed step'

    def run(self, ctx):
        raise NotImplementedError

    # Helpers shared by every step -----------------------------------------
    def say(self, ctx, message):
        ctx.say(f'{self.name}: {message}')

    def create_or_pretend(self, ctx, cls, **payload):
        """Create an m3ter object via the SDK, or just print the payload on a dry run.

        cls is an m3sdk class (Account, Plan, ...). Returns the created object,
        or a stand-in dict with a fake id when dry-running so later steps can
        still chain off it.
        """
        label = cls.__name__
        if ctx.dry_run:
            self.say(ctx, f'DRY RUN would create {label}: {json.dumps(payload, indent=2)}')
            return SimpleNamespace(id=f'dry-run-{label.lower()}', **payload)
        obj = cls.create(ctx.m3, **payload)
        self.say(ctx, f'created {label} {getattr(obj, "code", "")} ({obj.id})')
        return obj


def run_steps(ctx, steps):
    """Run the bricks in order; stop at the first failure (m3sh does the same).

    The log on ctx says how far it got, and ctx.state holds everything created
    so far — useful when deciding whether to re-run or clean up.
    """
    for step in steps:
        ctx.say(f'--- {step.name}')
        step.run(ctx)
    ctx.say('--- done')
    return ctx
