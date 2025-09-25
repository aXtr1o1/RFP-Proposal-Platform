import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/app/supabase/admin'

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { uuid, pdfUrl, comments } = body

    if (!uuid || !pdfUrl || !Array.isArray(comments)) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 })
    }

    // clear previous for this uuid (idempotent saves)
    const { error: delErr } = await supabaseAdmin.from('proposal_comments').delete().eq('uuid', uuid)
    if (delErr) {
      console.error('Delete error:', delErr)
      return NextResponse.json({ error: 'Failed to clear existing comments' }, { status: 500 })
    }

    const rows = comments.map((c: any) => ({
      uuid,
      proposal_url: pdfUrl,
      comments: c.comment,
      selected_content: c.selectedText,
    }))

    const { data, error } = await supabaseAdmin
      .from('proposal_comments')
      .insert(rows)
      .select()

    if (error) {
      console.error('Insert error:', error)
      return NextResponse.json({ error: 'Failed to save comments' }, { status: 500 })
    }

    return NextResponse.json({
      success: true,
      message: `${data.length} comments saved successfully`,
      data
    })
  } catch (e:any) {
    console.error('POST /supabase-comments error:', e)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const uuid = searchParams.get('uuid')
    if (!uuid) {
      return NextResponse.json({ error: 'UUID is required' }, { status: 400 })
    }

    const { data, error } = await supabaseAdmin
      .from('proposal_comments')
      .select('*')
      .eq('uuid', uuid)
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Fetch error:', error)
      return NextResponse.json({ error: 'Failed to fetch comments' }, { status: 500 })
    }

    return NextResponse.json({ success: true, comments: data })
  } catch (e:any) {
    console.error('GET /supabase-comments error:', e)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
