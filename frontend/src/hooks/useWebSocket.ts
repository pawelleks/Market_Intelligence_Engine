
import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketOptions {
    url: string;
    onMessage?: (data: any) => void;
    onOpen?: () => void;
    onClose?: () => void;
    onError?: (event: Event) => void;
    shouldConnect?: boolean;
    reconnectInterval?: number;
}

export const useWebSocket = ({
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    shouldConnect = true,
    reconnectInterval = 3000
}: WebSocketOptions) => {
    const [status, setStatus] = useState<string>('Disconnected');
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

    const connect = useCallback(() => {
        if (!shouldConnect) return;

        try {
            setStatus('Connecting...');
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setStatus('Connected');
                onOpen?.();
            };

            ws.onmessage = (event) => {
                if (onMessage) {
                    try {
                        const data = JSON.parse(event.data);
                        onMessage(data);
                    } catch (e) {
                        console.error("WebSocket parse error:", e);
                    }
                }
            };

            ws.onclose = () => {
                setStatus('Disconnected');
                onClose?.();
                // Auto-reconnect
                reconnectTimeoutRef.current = setTimeout(() => {
                    connect();
                }, reconnectInterval);
            };

            ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                onError?.(error);
                ws.close();
            };

        } catch (e) {
            console.error("WebSocket connection error:", e);
            setStatus('Error');
            reconnectTimeoutRef.current = setTimeout(() => {
                connect();
            }, reconnectInterval);
        }
    }, [url, shouldConnect, onMessage, onOpen, onClose, onError, reconnectInterval]);

    useEffect(() => {
        if (shouldConnect) {
            connect();
        }
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [connect, shouldConnect]);

    return { status, ws: wsRef.current };
};
