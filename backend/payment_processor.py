from typing import Any
from a2a.types import Task, TaskState, TaskStatus, TaskUpdater
from ucp_sdk.models.schemas.shopping.types.payment_instrument import PaymentInstrument


class MockPaymentProcessor:
  """Mock Payment Processor simulating calls from Merchant Agent to MPP Agent."""

  def process_payment(
      self, payment_data: PaymentInstrument, risk_data: Any | None = None
  ):
    """Process the payment."""
    # this should invoke the Merchant Payment Processor to validate the payment
    task = TaskUpdater(
        context_id="a unique context id",
        id="a unique task id",
        status=TaskStatus(state=TaskState.completed),
    )
    # return a task that represents the payment processing has completed
    return task.current_state