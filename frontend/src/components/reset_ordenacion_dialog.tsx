"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RotateCcw, Loader2, AlertTriangle } from "lucide-react";
import { resetOrdenacion } from "@/lib/eleccion-service";
import { toast } from "@/hooks/use-toast";

interface ResetOrdenacionDialogProps {
  onReset?: () => void;
  variant?: "outline" | "destructive" | "ghost";
  size?: "sm" | "default";
}

const CONFIRM_WORD = "RESETEAR";

export function ResetOrdenacionDialog({
  onReset,
  variant = "outline",
  size = "sm",
}: ResetOrdenacionDialogProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const confirmed = input.trim() === CONFIRM_WORD;

  const handleReset = async () => {
    if (!confirmed) return;
    setLoading(true);
    try {
      const res = await resetOrdenacion();
      if (res.ok) {
        toast({
          title: "Ordenación reiniciada",
          description: res.mensaje,
        });
        setOpen(false);
        setInput("");
        onReset?.();
      }
    } catch (err) {
      toast({
        title: "Error al resetear",
        description: err instanceof Error ? err.message : "Error inesperado.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!loading) {
          setOpen(v);
          if (!v) setInput("");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant={variant} size={size} className="text-destructive hover:text-destructive border-destructive/30 hover:border-destructive/60 hover:bg-destructive/5">
          <RotateCcw className="w-4 h-4 mr-2" />
          Resetear ordenación
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="w-5 h-5" />
            Resetear toda la ordenación
          </DialogTitle>
          <DialogDescription className="space-y-2 pt-1">
            <span className="block">
              Esta acción eliminará <strong>todas las asignaciones confirmadas y todos los borradores</strong> del sistema. No se puede deshacer.
            </span>
            <span className="block text-destructive/80 font-medium">
              Para confirmar, escribe <strong>{CONFIRM_WORD}</strong> en el campo de abajo.
            </span>
          </DialogDescription>
        </DialogHeader>

        <div className="py-2">
          <Input
            placeholder={`Escribe ${CONFIRM_WORD} para continuar`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && confirmed && handleReset()}
            className="font-mono"
            autoFocus
          />
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setOpen(false); setInput(""); }}
            disabled={loading}
          >
            Cancelar
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleReset}
            disabled={!confirmed || loading}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RotateCcw className="w-4 h-4 mr-2" />
            )}
            Resetear todo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}