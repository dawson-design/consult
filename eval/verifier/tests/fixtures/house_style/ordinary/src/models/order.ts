export type OrderStatus = "placed" | "in_progress" | "dispatched" | "delivered" | "cancelled";
export interface Order {
  id: string;
  customerId: string | null;
  status: OrderStatus;
  total: number;
  trackingNumber?: string | null;
  cancelReason?: string | null;
  restockingFee?: number | null;
  isCancelled: boolean;
}
export class OrderError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
