import { useCallback, useState } from 'react';
import { toPng } from 'html-to-image';

/**
 * Hook to handle social media image export from a DOM element.
 * 
 * @param {React.RefObject} ref - Reference to the DOM element to export.
 * @param {string} filename - The name of the file to be downloaded.
 * @returns {Object} - { exportImage, isExporting, error }
 */
export const useSocialExport = (ref, filename = 'social-share.png') => {
    const [isExporting, setIsExporting] = useState(false);
    const [error, setError] = useState(null);

    const exportImage = useCallback(async () => {
        if (!ref.current) {
            setError('No reference provided for export.');
            return;
        }

        setIsExporting(true);
        setError(null);

        try {
            const dataUrl = await toPng(ref.current, {
                pixelRatio: 2, // High resolution for text and charts
                cacheBust: true,
                style: {
                    // Ensure the element is visible during capture if it's off-screen
                    visibility: 'visible',
                    display: 'block'
                }
            });

            // Trigger download
            const link = document.createElement('a');
            link.download = filename.endsWith('.png') ? filename : `${filename}.png`;
            link.href = dataUrl;
            link.click();
        } catch (err) {
            console.error('Social export failed:', err);
            setError(err.message || 'Failed to generate social image.');
        } finally {
            setIsExporting(false);
        }
    }, [ref, filename]);

    return { exportImage, isExporting, error };
};

export default useSocialExport;
