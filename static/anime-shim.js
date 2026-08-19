window.anime = function anime(options) {
    const targets = Array.isArray(options.targets)
        ? options.targets
        : [options.targets];

    targets.filter(Boolean).forEach((target) => {
        if (options.opacity !== undefined) {
            target.style.opacity = Array.isArray(options.opacity)
                ? options.opacity[1]
                : options.opacity;
        }

        if (options.translateY !== undefined) {
            const value = Array.isArray(options.translateY)
                ? options.translateY[1]
                : options.translateY;
            target.style.transform = `translateY(${value}px)`;
        }

        if (options.rotate !== undefined) {
            target.style.transform = target.style.transform.replace(/rotate\([^)]*\)/, "").trim();
            target.style.transform = `${target.style.transform} rotate(${options.rotate}deg)`.trim();
        }
    });
};
