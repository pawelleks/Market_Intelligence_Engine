
import { useEffect } from 'react';

export const usePageTitle = (title) => {
    useEffect(() => {
        const prevTitle = document.title;
        document.title = `${title} | Market Intelligence Engine`;
        return () => {
            document.title = prevTitle;
        };
    }, [title]);
};
