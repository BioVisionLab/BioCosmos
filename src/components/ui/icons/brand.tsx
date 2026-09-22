import { Detail, IconBase, type IconProps } from "./IconBase";

// ---------------------------------------------------------------------------
// The landing-page section marks. Same grid, same two tones as the domain
// icons, so the home page and the species pages read as one product — which is
// the whole reason the emoji these replace had to go: 🦋 renders as a
// different drawing on every platform and cannot be themed at all.
// ---------------------------------------------------------------------------

/** Featured butterflies. */
export function ButterflyIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M11.6 6.4C10.6 4.6 9.4 3.6 8.2 3.1" />
          <path d="M12.4 6.4C13.4 4.6 14.6 3.6 15.8 3.1" />
          <circle cx="7.6" cy="8.6" r="1.1" />
          <circle cx="16.4" cy="8.6" r="1.1" />
        </>
      }
    >
      <path d="M12 7.2C8.9 5.2 5.6 3.9 3.1 4.5C2 6.9 2.9 9.9 5.1 11.6C7.5 11.8 10 11.4 12 11.2Z" />
      <path d="M12 7.2C15.1 5.2 18.4 3.9 20.9 4.5C22 6.9 21.1 9.9 18.9 11.6C16.5 11.8 14 11.4 12 11.2Z" />
      <path d="M12 11.5C9.6 12 6.9 12.6 5.5 14.2C4.9 16.1 6.4 18 8.7 18.2C10.4 17.2 11.4 15.3 12 13.5Z" />
      <path d="M12 11.5C14.4 12 17.1 12.6 18.5 14.2C19.1 16.1 17.6 18 15.3 18.2C13.6 17.2 12.6 15.3 12 13.5Z" />
      <path d="M12 6.4V17.2" />
      <Detail>
        <path d="M11 8.6C9.2 8.4 7.2 8.2 5.4 8.4" />
        <path d="M13 8.6C14.8 8.4 16.8 8.2 18.6 8.4" />
      </Detail>
    </IconBase>
  );
}

/**
 * Explore by appearance.
 *
 * A wing carrying colour swatches, rather than an artist's palette: the search
 * this heads is over wing colour and pattern, and a palette would be a generic
 * mark that says "colour" and nothing about what is being searched.
 */
export function AppearanceIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <circle cx="9.4" cy="9.6" r="1.6" />
          <circle cx="14.6" cy="8" r="1.6" />
          <circle cx="12.8" cy="14" r="1.6" />
        </>
      }
    >
      <path d="M4.4 12.4C4.4 7 8.4 3.4 13.6 3.6C18 3.8 20.4 7 20 10.8C19.4 15.4 16 19.6 11 20.4C6.8 20.8 4.4 17.2 4.4 12.4Z" />
      <Detail>
        <path d="M4.6 14.2C8.4 13.4 12 15.6 13.2 19.8" />
      </Detail>
    </IconBase>
  );
}

/** Collection summary. */
export function SummaryIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M3.6 19.6H21" />
          <path d="M3.6 4.4V19.6" />
          <path d="M2.4 15.4H3.6" />
          <path d="M2.4 11H3.6" />
          <path d="M2.4 6.6H3.6" />
        </>
      }
    >
      <rect x="5.8" y="12.4" width="3.6" height="7.2" rx="1" />
      <rect x="10.4" y="7.6" width="3.6" height="12" rx="1" />
      <rect x="15" y="10.2" width="3.6" height="9.4" rx="1" />
    </IconBase>
  );
}
