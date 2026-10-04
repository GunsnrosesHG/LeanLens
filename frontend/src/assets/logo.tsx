import { type SVGProps } from 'react'
import { cn } from '@/lib/utils'

/** LeanLens lens mark — matches public/favicon.svg and brand/ assets. */
export function Logo({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      id='leanlens-logo'
      viewBox='0 0 64 64'
      xmlns='http://www.w3.org/2000/svg'
      height='24'
      width='24'
      fill='none'
      className={cn('size-6', className)}
      {...props}
    >
      <title>LeanLens</title>
      <circle
        cx='32'
        cy='32'
        r='15'
        stroke='currentColor'
        strokeWidth='4.5'
        className='text-blue-500'
      />
      <ellipse
        cx='32'
        cy='32'
        rx='7.2'
        ry='4.5'
        fill='currentColor'
        className='text-blue-500'
        transform='rotate(-24 32 32)'
      />
      <circle cx='40' cy='21' r='2.8' className='fill-blue-300' />
    </svg>
  )
}
