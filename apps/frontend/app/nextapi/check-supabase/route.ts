import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/app/supabase/admin'

export async function GET() {
  try {
    const { error } = await supabaseAdmin
      .from('proposal_comments')
      .select('id', { count: 'exact', head: true })
      .limit(1)

    if (error) {
      console.error('Supabase connection error:', error)
      return NextResponse.json({ connected: false, error: error.message }, { status: 500 })
    }

    return NextResponse.json({
      connected: true,
      message: 'Supabase connection successful',
      timestamp: new Date().toISOString()
    })
  } catch (e:any) {
    console.error('Supabase check failed:', e)
    return NextResponse.json({ connected: false, error: 'Failed to connect to Supabase' }, { status: 500 })
  }
}
