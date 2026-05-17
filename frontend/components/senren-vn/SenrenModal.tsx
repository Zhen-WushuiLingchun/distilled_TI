"use client";

import type { ReactNode } from "react";

interface SenrenModalProps {
  title: string;
  children: ReactNode;
  onClose: () => void;
}

export function SenrenModal({ title, children, onClose }: SenrenModalProps) {
  return (
    <div className="senren-vn-modal-backdrop" onClick={onClose}>
      <div className="senren-vn-modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button onClick={onClose}>Close</button>
        </header>
        {children}
      </div>
    </div>
  );
}
