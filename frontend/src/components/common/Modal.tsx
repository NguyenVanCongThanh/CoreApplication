"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

// --- Root Component ---
interface EntityModalProps extends React.ComponentPropsWithoutRef<
  typeof Dialog
> {
  onClose?: () => void;
}

const ModalRoot = ({
  children,
  open,
  onOpenChange,
  onClose,
  ...props
}: EntityModalProps) => {
  const handleOpenChange = (open: boolean) => {
    if (onOpenChange) onOpenChange(open);
    if (!open && onClose) onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange} {...props}>
      <DialogContent className="sm:max-w-[525px] flex flex-col gap-4">
        {children}
      </DialogContent>
    </Dialog>
  );
};
ModalRoot.displayName = "Modal";

// --- Header ---
const ModalHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <DialogHeader className={cn("space-y-1.5", className)} {...props} />
);
ModalHeader.displayName = "ModalHeader";

// --- Title ---
const ModalTitle = React.forwardRef<
  React.ElementRef<typeof DialogTitle>,
  React.ComponentPropsWithoutRef<typeof DialogTitle>
>(({ className, ...props }, ref) => (
  <DialogTitle
    ref={ref}
    className={cn("text-lg font-semibold", className)}
    {...props}
  />
));
ModalTitle.displayName = "ModalTitle";

// --- Description ---
const ModalDescription = React.forwardRef<
  React.ElementRef<typeof DialogDescription>,
  React.ComponentPropsWithoutRef<typeof DialogDescription>
>(({ className, ...props }, ref) => (
  <DialogDescription
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
ModalDescription.displayName = "ModalDescription";

// --- Body ---
const ModalBody = ({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof ScrollArea>) => (
  <ScrollArea className={cn("max-h-[60vh] pr-4", className)} {...props}>
    {children}
  </ScrollArea>
);
ModalBody.displayName = "ModalBody";

// --- Footer ---
const ModalFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <DialogFooter
    className={cn("flex gap-2 sm:justify-end mt-2", className)}
    {...props}
  />
);
ModalFooter.displayName = "ModalFooter";

// --- Export Compound Component ---
export { ModalHeader, ModalTitle, ModalDescription, ModalBody, ModalFooter };
