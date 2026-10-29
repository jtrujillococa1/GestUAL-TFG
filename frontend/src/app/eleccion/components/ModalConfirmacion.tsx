import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
  } from "@/components/ui/dialog";
  import { Button } from "@/components/ui/button";
  import { Loader2 } from "lucide-react";
  
  interface ModalConfirmacionProps {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
    loading: boolean;
  }
  
  export function ModalConfirmacion({ open, onClose, onConfirm, loading }: ModalConfirmacionProps) {
    return (
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Turno</DialogTitle>
            <DialogDescription>
              ¿Estás seguro de que quieres confirmar tu selección? Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={onClose} disabled={loading}>
              Cancelar
            </Button>
            <Button onClick={onConfirm} disabled={loading}>
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Confirmar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }