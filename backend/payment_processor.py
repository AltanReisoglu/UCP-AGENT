from typing import Any
from a2a.types import Task, TaskState, TaskStatus
from ucp_sdk.models.schemas.shopping.types.payment_instrument import PaymentInstrument


class MockPaymentProcessor:
  """Mock Payment Processor simulating calls from Merchant Agent to MPP Agent."""

  def process_payment(
      self, payment_data: PaymentInstrument, risk_data: Any | None = None
  ) -> Task:
    """Process the payment."""
    # this should invoke the Merchant Payment Processor to validate the payment
    # For demo purposes, we return a completed task
    task = Task(
        context_id="mock-context-id",
        id="mock-task-id",
        status=TaskStatus(state=TaskState.completed),
    )
    # return a task that represents the payment processing has completed
    return task