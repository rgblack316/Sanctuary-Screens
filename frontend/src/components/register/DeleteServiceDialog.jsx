import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { formatCount, formatDate, formatMoney } from "@/lib/api";

export const DeleteServiceDialog = ({ service, currency, onCancel, onConfirm }) => (
  <AlertDialog open={!!service} onOpenChange={(o) => !o && onCancel()}>
    <AlertDialogContent className="border-[#222B3E] bg-[#121620]" data-testid="delete-service-dialog">
      <AlertDialogHeader>
        <AlertDialogTitle className="font-display">Delete {service && formatDate(service.service_date)}?</AlertDialogTitle>
        <AlertDialogDescription>
          This removes the record ({service?.service_label || "Service"} · attendance {formatCount(service?.attendance) ?? "—"} · offering {formatMoney(service?.offering, currency) ?? "—"}).
          If it is on the display, the display switches to the latest remaining service.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel data-testid="delete-service-cancel">Cancel</AlertDialogCancel>
        <AlertDialogAction onClick={onConfirm} data-testid="delete-service-confirm" className="bg-rose-600 hover:bg-rose-500">Delete</AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);
