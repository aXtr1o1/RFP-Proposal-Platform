export const runtime = "nodejs";

import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/app/supabase/admin";

export async function POST(req: Request) {
  try {
    const form = await req.formData();

    const uuid = (form.get("uuid") as string) || "";
    const config = (form.get("config") as string) || "";

    const rfpFiles = form.getAll("rfpFiles") as File[];
    const supportingFiles = form.getAll("supportingFiles") as File[];

    console.log('Processing upload for UUID:', uuid);
    console.log('RFP files count:', rfpFiles.length);
    console.log('Supporting files count:', supportingFiles.length);

    if (!uuid) {
      return NextResponse.json({ error: "uuid required" }, { status: 400 });
    }

    // Validate files are provided
    if (rfpFiles.length === 0 && supportingFiles.length === 0) {
      return NextResponse.json({ error: "No files provided" }, { status: 400 });
    }

    // File size validation (50MB max)
    const MAX_FILE_SIZE = 50 * 1024 * 1024;
    const allFiles = [...rfpFiles, ...supportingFiles];
    
    for (const file of allFiles) {
      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json({ 
          error: `File ${file.name} exceeds 50MB size limit` 
        }, { status: 400 });
      }
      
      if (file.size === 0) {
        return NextResponse.json({ 
          error: `File ${file.name} is empty` 
        }, { status: 400 });
      }
    }

    // Helper function to upload files to Supabase storage
    const uploadOne = async (
      bucket: string,
      file: File,
      index: number
    ): Promise<{ name: string; url: string; size: number }> => {
      try {
        const arrayBuffer = await file.arrayBuffer();
        const buffer = Buffer.from(arrayBuffer);
        
        // Create unique file path: uuid/timestamp_index_filename
        const timestamp = Date.now();
        const sanitizedFileName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
        const filePath = `${uuid}/${timestamp}_${index}_${sanitizedFileName}`;

        console.log(`Uploading ${file.name} to bucket: ${bucket}, path: ${filePath}`);

        // Upload to Supabase storage
        const { data: uploadData, error: uploadError } = await supabaseAdmin.storage
          .from(bucket)
          .upload(filePath, buffer, {
            contentType: file.type || "application/octet-stream",
            upsert: true, // Allow overwrite if file exists
          });

        if (uploadError) {
          console.error(`Upload error for ${file.name}:`, uploadError);
          throw new Error(`Failed to upload ${file.name}: ${uploadError.message}`);
        }

        console.log(`Successfully uploaded ${file.name}:`, uploadData);

        // Get public URL
        const { data: urlData } = supabaseAdmin.storage
          .from(bucket)
          .getPublicUrl(filePath);

        if (!urlData.publicUrl) {
          throw new Error(`Failed to get public URL for ${file.name}`);
        }

        return { 
          name: file.name, 
          url: urlData.publicUrl,
          size: file.size
        };

      } catch (error) {
        console.error(`Error processing file ${file.name}:`, error);
        throw error;
      }
    };

    // Upload all RFP files
    console.log('Starting RFP file uploads...');
    const rfpResults = await Promise.allSettled(
      rfpFiles.map((file, index) => uploadOne("rfp", file, index))
    );

    // Upload all supporting files
    console.log('Starting supporting file uploads...');
    const supportingResults = await Promise.allSettled(
      supportingFiles.map((file, index) => uploadOne("supporting", file, index))
    );

    // Check for upload failures
    const failedRfpUploads = rfpResults.filter(result => result.status === 'rejected');
    const failedSupportingUploads = supportingResults.filter(result => result.status === 'rejected');

    if (failedRfpUploads.length > 0 || failedSupportingUploads.length > 0) {
      console.error('Some uploads failed:');
      failedRfpUploads.forEach((result, index) => {
        if (result.status === 'rejected') {
          console.error(`RFP file ${index}:`, result.reason);
        }
      });
      failedSupportingUploads.forEach((result, index) => {
        if (result.status === 'rejected') {
          console.error(`Supporting file ${index}:`, result.reason);
        }
      });
    }

    // Extract successful uploads
    const successfulRfpUploads = rfpResults
      .filter((result): result is PromiseFulfilledResult<{ name: string; url: string; size: number }> => 
        result.status === 'fulfilled'
      )
      .map(result => result.value);

    const successfulSupportingUploads = supportingResults
      .filter((result): result is PromiseFulfilledResult<{ name: string; url: string; size: number }> => 
        result.status === 'fulfilled'
      )
      .map(result => result.value);

    console.log('Successful RFP uploads:', successfulRfpUploads.length);
    console.log('Successful supporting uploads:', successfulSupportingUploads.length);

    // Prepare data for database update - just the first URL as string
    const rfpFileUrls = successfulRfpUploads.map(file => file.url);
    const supportingFileUrls = successfulSupportingUploads.map(file => file.url);
    
    const rfpFileData = successfulRfpUploads.length > 0 ? successfulRfpUploads[0].url : null;
    const supportingFileData = successfulSupportingUploads.length > 0 ? successfulSupportingUploads[0].url : null;

    console.log('Saving to database with file URLs...');
    console.log('RFP URLs:', rfpFileUrls);
    console.log('Supporting URLs:', supportingFileUrls);

    // Try to update existing record first
    const { data: updateData, error: updateError } = await supabaseAdmin
      .from("Data_Table")
      .update({
        RFP_Files: rfpFileData,
        Supporting_Files: supportingFileData,
      })
      .eq("uuid", uuid)
      .select();

    let finalData = updateData;

    // If no rows were updated, insert a new record
    if (!updateError && (!updateData || updateData.length === 0)) {
      console.log('No existing record found, creating new record...');
      
      const { data: insertData, error: insertError } = await supabaseAdmin
        .from("Data_Table")
        .insert({
          uuid: uuid,
          RFP_Files: rfpFileData,
          Supporting_Files: supportingFileData,
        })
        .select();

      if (insertError) {
        console.error('Database insert error:', insertError);
        throw new Error(`Database insert failed: ${insertError.message}`);
      }

      finalData = insertData;
      console.log('New record created successfully:', insertData);
    } else if (updateError) {
      console.error('Database update error:', updateError);
      throw new Error(`Database update failed: ${updateError.message}`);
    } else {
      console.log('Existing record updated successfully:', updateData);
    }

    // Return success response
    const response = {
      success: true,
      uuid,
      config,
      rfp: {
        uploaded: successfulRfpUploads,
        failed: failedRfpUploads.length,
        total: rfpFiles.length
      },
      supporting: {
        uploaded: successfulSupportingUploads,
        failed: failedSupportingUploads.length,
        total: supportingFiles.length
      },
      summary: {
        totalFilesProcessed: allFiles.length,
        totalFilesUploaded: successfulRfpUploads.length + successfulSupportingUploads.length,
        totalFilesFailed: failedRfpUploads.length + failedSupportingUploads.length
      }
    };

    console.log('Upload process completed:', response.summary);
    
    return NextResponse.json(response);

  } catch (err: any) {
    console.error("Upload process failed:", err);
    
    // More detailed error response
    return NextResponse.json(
      { 
        error: "upload_failed", 
        detail: err.message || "Unknown error occurred",
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
}