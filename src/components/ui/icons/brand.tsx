import { Detail, Dot, IconBase, type IconProps } from "./IconBase";

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
          <path d="M11.6 6C10.6 4.2 9.4 3.3 8.2 2.9" />
          <path d="M12.4 6C13.4 4.2 14.6 3.3 15.8 2.9" />
        </>
      }
    >
      <path d="M12 7C8.9 5 5.6 3.7 3.1 4.3C2 6.7 2.9 9.4 5.1 11C7.5 11.5 10 11.4 12 11.2Z" />
      <path d="M12 7C15.1 5 18.4 3.7 20.9 4.3C22 6.7 21.1 9.4 18.9 11C16.5 11.5 14 11.4 12 11.2Z" />
      {/* The hindwings start on the forewings' trailing edge, not below it: a
          butterfly's wings overlap at the base, and with a gap between them
          the glyph read as two moths stacked. Each hindwing is open along its
          costa -- the forewing edge above is that line. */}
      <path d="M6.5 11.2C5 12.7 4.7 15.4 5.7 17.2C6.5 18.6 7.8 19.2 8.7 19.1C10.4 18.1 11.4 16.3 12 14.6" />
      <path d="M17.5 11.2C19 12.7 19.3 15.4 18.3 17.2C17.5 18.6 16.2 19.2 15.3 19.1C13.6 18.1 12.6 16.3 12 14.6" />
      <path d="M12 6V18.2" />
      <Detail>
        <path d="M11 8.2C9.2 8 7.2 7.8 5.4 8" />
        <path d="M13 8.2C14.8 8 16.8 7.8 18.6 8" />
      </Detail>
      {/* Forewing spots. Previously 1.1-radius circles in the supporting tone
          with a vein running through their centres, which filled them solid —
          a stroked circle with a 1.0 hole is what `Dot` exists for. Moved
          clear of the vein and made the subject, which is what a wing marking
          is. */}
      <Dot cx={7.8} cy={9.4} r={0.7} />
      <Dot cx={16.2} cy={9.4} r={0.7} />
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

/**
 * Collection summary.
 *
 * Narrower bars than the obvious ones: at 3.6 wide the 1.0 channels between
 * them were narrower than the two stroke halves facing across them, so the
 * three bars welded into one block — and this glyph renders at 24px on the
 * landing page, where that channel is a single device pixel. 3.0 wide on a
 * 4.9 pitch opens it to 1.9.
 */
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
      <rect x="5.8" y="12.4" width="3" height="7.2" rx="1" />
      <rect x="10.7" y="7.6" width="3" height="12" rx="1" />
      <rect x="15.6" y="10.2" width="3" height="9.4" rx="1" />
    </IconBase>
  );
}

/**
 * Species diversity by country.
 *
 * A globe with its meridian and parallels in the supporting tone, and one
 * continent-like patch as the subject: the section is about where species
 * were recorded, not about navigation, so no pin.
 */
export function GlobeIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M3.4 12H20.6" />
          <path d="M12 3.4C10.2 6 9.6 9 9.6 12C9.6 15 10.2 18 12 20.6" />
          <path d="M12 3.4C13.8 6 14.4 9 14.4 12C14.4 15 13.8 18 12 20.6" />
        </>
      }
    >
      <circle cx="12" cy="12" r="8.6" />
      {/* Two closed landmasses, each set in a cell of the graticule so no
          grid line runs through it — which is why the meridians are drawn
          narrow. The single open stroke this replaces crossed a meridian and
          read as a question mark. */}
      <Detail>
        <path d="M6.8 7.2C7.9 7.1 8.6 7.8 8.4 8.7C8.2 9.4 7.6 9.6 7.4 10.2C7.2 10.8 6.4 10.9 6 10.4C5.6 9.9 5.3 9.5 5.4 8.7C5.5 7.8 6.1 7.3 6.8 7.2Z" />
        <path d="M16.6 13.2C17.6 13.1 18.6 13.6 18.6 14.6C18.6 15.6 17.8 16.6 17 16.6C16.4 16.6 16.3 16 16 15.5C15.7 15 15.6 14.4 15.8 13.9C15.9 13.5 16.2 13.3 16.6 13.2Z" />
      </Detail>
    </IconBase>
  );
}
